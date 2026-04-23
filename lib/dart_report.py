"""DART 사업보고서 본문 추출 + Gemini 요약"""
import urllib.request, io, zipfile, json, os, re, time
from xml.etree import ElementTree as ET
from datetime import date, timedelta

from lib.retry import retry
from lib.cache import TTLCache
from lib.dart_corp import find_corp_by_stock_code
from lib.gemini import generate as gemini_generate
from lib.http_utils import build_url, safe_exception_text, urlopen_sanitized

DART_BASE = 'https://opendart.fss.or.kr/api'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
DART_SECRET_PARAMS = ('crtfc_key',)

# 사업보고서는 분기당 1회 갱신 — 24시간 캐시
_summary_cache = TTLCache(ttl=24 * 3600)
_doc_cache = TTLCache(ttl=24 * 3600)


def _api_key() -> str:
    key = os.environ.get('DART_API_KEY', '').strip()
    if not key:
        raise ValueError('DART_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def _find_latest_business_report(corp_code: str) -> dict | None:
    """corp_code → 가장 최근 사업보고서(A001) 공시 1건 또는 None.
    사업보고서는 연 1회 발간되므로 최근 18개월 검색."""
    today = date.today()
    bgn = (today - timedelta(days=540)).strftime('%Y%m%d')
    end = today.strftime('%Y%m%d')

    params = {
        'crtfc_key': _api_key(),
        'corp_code': corp_code,
        'bgn_de': bgn,
        'end_de': end,
        'pblntf_detail_ty': 'A001',
        'page_count': '10',
        'sort': 'date',
        'sort_mth': 'desc',
    }
    request_url = build_url(DART_BASE, 'list.json', params)

    def _call():
        req = urllib.request.Request(request_url, headers=HEADERS)
        with urlopen_sanitized(req, timeout=10, secret_query_keys=DART_SECRET_PARAMS) as r:
            return json.loads(r.read().decode('utf-8'))

    data = retry(_call)
    items = data.get('list') or []
    if not items:
        return None
    return items[0]


def _fetch_document_text(rcept_no: str) -> str:
    """공시서류 원문 zip → 가장 큰 XML 파일만 텍스트 디코딩 (본문은 보통 메인 파일 1개에 집중)."""
    cached = _doc_cache.get(rcept_no)
    if cached is not None:
        return cached

    request_url = build_url(DART_BASE, 'document.xml', {
        'crtfc_key': _api_key(),
        'rcept_no': rcept_no,
    })

    def _call():
        req = urllib.request.Request(request_url, headers=HEADERS)
        with urlopen_sanitized(req, timeout=30, secret_query_keys=DART_SECRET_PARAMS) as r:
            return r.read()

    raw = retry(_call)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        xml_infos = [info for info in zf.infolist()
                     if info.filename.lower().endswith('.xml')]
        if not xml_infos:
            return ''
        # 파일 크기 내림차순 — 가장 큰 XML(본문)만 파싱
        xml_infos.sort(key=lambda i: i.file_size, reverse=True)
        main_info = xml_infos[0]
        with zf.open(main_info) as f:
            data = f.read()

    text = ''
    for enc in ('utf-8', 'euc-kr', 'cp949'):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    _doc_cache.set(rcept_no, text)
    return text


def _strip_tags(s: str) -> str:
    """간이 XML/HTML 태그 제거 + 공백 정리."""
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&quot;', '"', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def _extract_business_overview(full_text: str, max_chars: int = 4000) -> str:
    """'1. 사업의 개요' 섹션만 추출 (다음 하위 항목 '2. 주요 제품 및 서비스' 직전까지).
    DART 원문 XML 구조: <TITLE>1. 사업의 개요</TITLE> ... <TITLE>2. 주요 제품 및 서비스</TITLE>."""
    start_patterns = [
        r'1\.\s*사업의\s*개요',
        r'가\.\s*사업의\s*개요',
    ]
    # 다음 하위 항목들 — 여러 표기 변형 허용
    end_patterns = [
        r'2\.\s*주요\s*제품',
        r'나\.\s*주요\s*제품',
        r'2\.\s*주요\s*서비스',
    ]

    start_m = None
    for p in start_patterns:
        m = re.search(p, full_text)
        if m:
            start_m = m
            break
    if not start_m:
        return ''

    rest = full_text[start_m.end():]
    end_pos = len(rest)
    for p in end_patterns:
        m = re.search(p, rest)
        if m and m.start() < end_pos:
            end_pos = m.start()

    section = full_text[start_m.start():start_m.end() + end_pos]
    cleaned = _strip_tags(section)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + ' …(이하 생략)'
    return cleaned


def _extract_section(full_text: str, header_patterns: list, max_chars: int = 8000) -> str:
    """본문에서 헤더 패턴부터 다음 대제목 전까지 추출.
    DART 사업보고서는 'I. 회사의 개요', 'II. 사업의 내용' 등 로마숫자 대제목 구조."""
    # 다음 대제목: 로마숫자 또는 한글 대문항
    next_header = r'(?:[IVX]+\.\s*[가-힣A-Za-z]|[가-힣]\.\s)'

    for pattern in header_patterns:
        # 헤더 매칭 — XML 태그 사이에 있을 수 있음
        m = re.search(pattern, full_text)
        if not m:
            continue
        start = m.start()
        # 헤더 다음 위치부터 다음 대제목 검색
        rest = full_text[m.end():]
        next_m = re.search(next_header, rest)
        end = m.end() + (next_m.start() if next_m else len(rest))
        section = full_text[start:end]
        cleaned = _strip_tags(section)
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + ' …(이하 생략)'
        return cleaned
    return ''


def summarize_business_report(stock_code: str, stock_name: str) -> dict:
    """종목코드 → 사업보고서 요약 결과.
    반환: {'corp_name', 'rcept_no', 'rcept_dt', 'report_nm', 'summary'} or {'error': ...}"""
    cache_key = f'summary:{stock_code}'
    cached = _summary_cache.get(cache_key)
    if cached is not None:
        print(f'[info] 캐시 히트: {stock_code}', flush=True)
        return cached

    t0 = time.time()
    corp = find_corp_by_stock_code(stock_code)
    print(f'[info] corp 매핑 {time.time()-t0:.1f}s: {corp}', flush=True)
    if not corp:
        return {'error': f'DART에 등록된 기업 정보 없음 (종목코드: {stock_code})'}

    t0 = time.time()
    report = _find_latest_business_report(corp['corp_code'])
    print(f'[info] 사업보고서 조회 {time.time()-t0:.1f}s: {report.get("rcept_no") if report else None}', flush=True)
    if not report:
        return {'error': '최근 사업보고서를 찾을 수 없습니다.'}

    rcept_no = report['rcept_no']
    t0 = time.time()
    full_text = _fetch_document_text(rcept_no)
    print(f'[info] 본문 다운로드 {time.time()-t0:.1f}s: {len(full_text):,}자', flush=True)
    if not full_text:
        return {'error': '사업보고서 본문을 가져올 수 없습니다.'}

    # 1. 사업의 내용 (II. 사업의 내용 ~ III. 직전)
    # 2. 이사의 경영진단 및 분석의견
    t0 = time.time()
    biz_content = _extract_section(full_text, [
        r'II\.\s*사업의\s*내용',
        r'2\.\s*사업의\s*내용',
    ], max_chars=8000)
    mgmt_analysis = _extract_section(full_text, [
        r'이사의\s*경영진단\s*및\s*분석\s*의견',
        r'경영진단\s*및\s*분석\s*의견',
    ], max_chars=5000)
    print(f'[info] 섹션 추출 {time.time()-t0:.1f}s: 사업의내용 {len(biz_content):,}자, 경영진단 {len(mgmt_analysis):,}자', flush=True)

    if not biz_content and not mgmt_analysis:
        return {'error': '사업보고서에서 해당 섹션을 추출할 수 없습니다.'}

    prompt = f"""너는 기업 정보 카드를 작성하는 편집자다. 사업보고서에서 핵심 사실만 뽑아
"- 라벨: 명사구" 형식의 10줄 카드를 만든다. 문장(서술형)이 아니라 사전 항목처럼 써야 한다.

# 절대 규칙
1. 각 줄은 반드시 `- {{라벨}}: {{명사구}}` 형식으로 시작한다.
2. 라벨(콜론 앞)은 2~5자의 한국어 명사 (예: 주요사업, 주요제품, 판매망, 실적동향).
3. 콜론 뒤는 **명사구**로만 작성. 마침표·서술어 금지.
   ❌ "~합니다", "~이다", "~했습니다", "~한다", "~됩니다", "~을 영위", "~을 보유"
   ✅ 명사·명사구로 끝남 (예: "글로벌 선도 지위 확보", "전년 대비 XX% 증가")
4. 회사명(주어)을 문장 앞에 쓰지 않는다.
5. 정확히 10줄, 한 줄에 한 항목.
6. 카테고리 라벨은 서로 겹치지 않게 10개 다른 관점으로.

# 라벨 후보 (본문에 맞게 선택)
사업구조 · 주요사업 · 주요제품 · 주요서비스 · 매출구성 · 주요고객 · 시장지위 · 경쟁력
생산시설 · 원재료 · 판매망 · 해외진출 · 연구개발 · 신규사업 · 사업전략
실적동향 · 재무상태 · 리스크요인 · 향후전망 · 경영진의견

# 올바른 예시 (이 스타일 그대로 따라라)
- 주요사업: 나노 단위 미세물 분석용 주사전자현미경(SEM) 및 주변기기 제조·판매
- 주요제품: SEM, Tabletop SEM, 이온밀러(IP), 이온코터(SPT)
- 신규제품: IP-SEM, 대기압 SEM(A SEM), AI-SEM
- 판매망: 국내 직판·딜러 병행, 해외 41개국 20개 대리점 간접판매
- 시장지위: Tabletop SEM 분야 글로벌 선도
- 경쟁력: 고성능 이온건 기술 내재화, AI-SEM 선도 기술
- 고객구조: 특정 고객·지역 의존도 낮은 다변화 구조
- 실적동향: 전방 반도체 투자 회복에 따른 매출 증가
- 리스크요인: 반도체 설비투자 사이클 의존, 환율 변동
- 경영진의견: Tabletop SEM 주력 포지셔닝 강화 + 응용제품 확장

# 잘못된 예시 (이렇게 쓰면 안 됨)
❌ "- 코셈은 나노 단위 미세물 분석을 위한 주사전자현미경을 제조합니다."  (주어+서술어)
❌ "- SEM과 주변기기를 제조 및 판매하고 있습니다."  (서술어)
❌ "- 핵심 제품으로는 SEM이 있습니다."  (서술어)
❌ "- 주요사업은 SEM 제조·판매입니다."  (서술어, 라벨 누락)

# 섹션별 역할
- '사업의 내용' 섹션에서 → 사업구조·제품·판매망·시장지위·경쟁력 카테고리
- '이사의 경영진단' 섹션에서 → 실적동향·재무상태·리스크요인·향후전망·경영진의견 카테고리

# 데이터 원칙
본문에 명시된 숫자·비율·고유명사(제품명, 지역명, 금액)는 가능한 한 그대로 인용.

=== 사업의 내용 ===
{biz_content if biz_content else '(추출 실패)'}

=== 이사의 경영진단 및 분석의견 ===
{mgmt_analysis if mgmt_analysis else '(추출 실패)'}

=== 작성 지시 ===
위 두 섹션을 읽고 아래 형식으로만 출력하라. 다른 텍스트(인사말, 머리말, 꼬리말, 빈 줄) 금지.
정확히 10줄. 각 줄은 반드시 `- ` 로 시작한 뒤 `라벨: 명사구`.
서술어('합니다', '이다', '있습니다', '영위' 등)와 주어(회사명) 절대 금지.

지금 바로 10줄 카드를 출력:"""

    try:
        t0 = time.time()
        summary = gemini_generate(prompt, max_output_tokens=512)
        print(f'[info] Gemini 요약 {time.time()-t0:.1f}s: {len(summary)}자', flush=True)
    except Exception as e:
        message = safe_exception_text(e)
        print(f'[info] Gemini 요약 실패: {message}', flush=True)
        return {'error': f'Gemini 요약 실패: {message}'}

    result = {
        'corp_name': corp['corp_name'],
        'rcept_no': rcept_no,
        'rcept_dt': report.get('rcept_dt', ''),
        'report_nm': report.get('report_nm', ''),
        'summary': summary,
    }
    _summary_cache.set(cache_key, result)
    return result
