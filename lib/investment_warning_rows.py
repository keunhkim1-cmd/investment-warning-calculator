"""KIND/Naver row-fetching for investment-warning status.

Constants, HTTP primitives, HTML parsers, and the high-level ``fetch_*``
helpers that retrieve investment-warning rows, trading-halt status, designation
disclosures, and Naver daily close prices. Pure data-access — no orchestration.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from html import unescape
import re
import urllib.parse

from lib.cache import TTLCache
from lib.http_client import BROWSER_HEADERS, request_bytes, request_text
from lib.investment_warning_dates import (
    format_kst_date,
    format_kst_date_years_before,
    normalize_naver_price_date,
    to_compact_date,
)
from lib.investment_warning_errors import InvestmentWarningStatusError
from lib.timeouts import KRX_KIND_TIMEOUT, NAVER_PRICE_TIMEOUT

# Per-stockCode invwarn-rows cache so the same-day repeat lookup survives a
# KIND outage via stale-on-error fallback. The orchestrator's _status_cache
# only helps after at least one successful fetch for the same stockCode+date.
_invwarn_rows_cache = TTLCache(ttl=10 * 60, name='kind-invwarn-rows', durable=True)

KIND_INVEST_WARNING_URL = 'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do'
KIND_DISCLOSURE_DETAILS_URL = 'https://kind.krx.co.kr/disclosure/details.do'
KIND_DISCLOSURE_VIEWER_URL = 'https://kind.krx.co.kr/common/disclsviewer.do'
KIND_TRADING_HALT_URL = 'https://kind.krx.co.kr/investwarn/tradinghaltissue.do'
NAVER_DAILY_PRICE_URL = 'https://api.finance.naver.com/siseJson.naver'
KIND_INVEST_WARNING_LOOKBACK_YEARS = 3
KIND_TRADING_HALT_MARKET_TYPES = ('1', '2', '6')

KIND_HEADERS = {
    **BROWSER_HEADERS,
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kind.krx.co.kr/',
}
KIND_POST_HEADERS = {
    **KIND_HEADERS,
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}
NAVER_HEADERS = {
    **BROWSER_HEADERS,
    'Accept': '*/*',
    'Referer': 'https://finance.naver.com/',
}


def fetch_investment_warning_rows(stock_code: str, now: datetime | date | None = None) -> list[dict]:
    end_date = format_kst_date(now)
    start_date = format_kst_date_years_before(now, KIND_INVEST_WARNING_LOOKBACK_YEARS)

    def _fetch() -> list[dict]:
        body = {
            'method': 'investattentwarnriskySub',
            'currentPageSize': '3000',
            'pageIndex': '1',
            'orderMode': '3',
            'orderStat': 'D',
            'searchCodeType': 'number',
            'searchCorpName': '',
            'repIsuSrtCd': f'A{stock_code}',
            'menuIndex': '2',
            'forward': 'invstwarnisu_down',
            'searchFromDate': end_date,
            'startDate': start_date,
            'endDate': end_date,
            'marketType': '',
        }
        html = kind_post_text(KIND_INVEST_WARNING_URL, body)
        rows = parse_kind_investment_warning_rows(html)
        if not rows and not is_kind_empty_result(html):
            raise InvestmentWarningStatusError('KIND 투자경고 응답을 해석할 수 없습니다.', 'PARSE')
        return rows

    return _invwarn_rows_cache.get_or_set(
        f'rows:{stock_code}:{end_date}',
        _fetch,
        allow_stale_on_error=True,
        max_stale=6 * 3600,
    )


def fetch_current_trading_halt_status(stock_code: str) -> dict:
    first_error: Exception | None = None
    for market_type in KIND_TRADING_HALT_MARKET_TYPES:
        body = {
            'method': 'searchTradingHaltIssueSub',
            'currentPageSize': '3000',
            'pageIndex': '1',
            'searchMode': '',
            'searchCodeType': '',
            'searchCorpName': '',
            'repIsuSrtCd': stock_code,
            'forward': 'tradinghaltissue_sub',
            'paxreq': '',
            'outsvcno': '',
            'marketType': market_type,
        }
        try:
            status = parse_kind_current_trading_halt_status(
                kind_post_text(KIND_TRADING_HALT_URL, body),
            )
        except Exception as exc:
            if first_error is None:
                first_error = exc
            continue
        if status['status'] == 'halted':
            return status

    if first_error is not None:
        return {
            'status': 'unknown',
            'reason': str(first_error) or 'KIND 매매거래정지 상태를 확인할 수 없습니다.',
        }

    return {'status': 'not_halted', 'reason': None}


def fetch_investment_warning_designation_disclosure(warning_row: dict) -> dict:
    disclosure = fetch_investment_warning_designation_disclosure_reference(warning_row)
    viewer_url = _url_with_params(KIND_DISCLOSURE_VIEWER_URL, {
        'method': 'search',
        'acptno': disclosure['acptNo'],
        'docno': '',
        'viewerhost': '',
        'viewerport': '',
    })
    viewer_html = kind_get_text(viewer_url)
    doc_no = parse_kind_disclosure_viewer_doc_no(viewer_html)
    if not doc_no:
        raise InvestmentWarningStatusError('KIND 지정 공시 문서번호를 찾을 수 없습니다.', 'PARSE')

    contents_url = _url_with_params(KIND_DISCLOSURE_VIEWER_URL, {
        'method': 'searchContents',
        'docNo': doc_no,
    })
    contents_html = kind_get_text(contents_url)
    disclosure_url = parse_kind_disclosure_document_url(contents_html)
    if not disclosure_url:
        raise InvestmentWarningStatusError('KIND 지정 공시 원문 경로를 찾을 수 없습니다.', 'PARSE')

    return {
        'url': disclosure_url,
        'html': kind_get_text(disclosure_url),
    }


def fetch_investment_warning_designation_disclosure_reference(warning_row: dict) -> dict:
    body = {
        'method': 'searchDetailsSub',
        'currentPageSize': '15',
        'pageIndex': '1',
        'orderMode': '1',
        'orderStat': 'D',
        'forward': 'details_sub',
        'searchCodeType': 'number',
        'repIsuSrtCd': f"A{warning_row['stockCode']}",
        'fromDate': warning_row['disclosureDate'],
        'toDate': warning_row['disclosureDate'],
        'reportNm': '투자경고종목지정',
    }
    html = kind_post_text(KIND_DISCLOSURE_DETAILS_URL, body)
    disclosures = parse_kind_disclosure_search_results(html)
    candidates = [
        disclosure for disclosure in disclosures
        if _is_designation_disclosure_title(disclosure['title'])
    ]
    if not candidates:
        raise InvestmentWarningStatusError('KIND 지정 공시를 상세검색에서 찾을 수 없습니다.', 'PARSE')
    candidates.sort(key=lambda d: '정정' not in normalize_disclosure_title(d['title']))
    return candidates[0]


def _is_designation_disclosure_title(title: str) -> bool:
    normalized = normalize_disclosure_title(title)
    if '투자경고종목지정' not in normalized:
        return False
    # '투자경고종목지정예고', '투자경고종목지정해제', '투자경고종목지정해제예고' 등은 본 지정 공시가 아님.
    if '지정예고' in normalized or '지정해제' in normalized:
        return False
    return True


def fetch_daily_close_prices(stock_code: str, start_date: str, end_date: str) -> list[dict]:
    url = _url_with_params(NAVER_DAILY_PRICE_URL, {
        'symbol': stock_code,
        'requestType': '1',
        'startTime': to_compact_date(start_date),
        'endTime': to_compact_date(end_date),
        'timeframe': 'day',
    })
    text = request_text(
        'naver',
        url,
        headers=NAVER_HEADERS,
        timeout=NAVER_PRICE_TIMEOUT,
        retries=1,
        encoding='utf-8',
        errors='replace',
    )
    return parse_naver_daily_close_prices(text)


def kind_post_text(url: str, body: dict[str, str]) -> str:
    raw = request_bytes(
        'krx',
        url,
        data=urllib.parse.urlencode(body).encode('utf-8'),
        method='POST',
        headers=KIND_POST_HEADERS,
        timeout=KRX_KIND_TIMEOUT,
        retries=1,
    )
    return decode_kind_text(raw)


def kind_get_text(url: str) -> str:
    raw = request_bytes(
        'krx',
        url,
        headers=KIND_HEADERS,
        timeout=KRX_KIND_TIMEOUT,
        retries=1,
    )
    return decode_kind_text(raw)


def decode_kind_text(raw: bytes, content_type: str = '') -> str:
    utf8_text = raw.decode('utf-8', errors='replace')
    charset = extract_charset(content_type) or extract_charset(utf8_text)
    if is_euc_kr_charset(charset) or '�' in utf8_text:
        return raw.decode('euc-kr', errors='replace')
    return utf8_text


def extract_charset(value: str) -> str | None:
    match = re.search(r'charset\s*=\s*["\']?([a-z0-9_-]+)', value, flags=re.I)
    return match.group(1).lower() if match else None


def is_euc_kr_charset(charset: str | None) -> bool:
    return charset in {'euc-kr', 'euckr', 'cp949'}


def parse_kind_investment_warning_rows(html: str) -> list[dict]:
    rows = []
    for row_html in re.findall(r'<tr\b[^>]*>([\s\S]*?)</tr>', html, flags=re.I):
        if re.search(r'<th\b', row_html, flags=re.I):
            continue
        cells = [clean_html_cell(match) for match in re.findall(r'<td\b[^>]*>([\s\S]*?)</td>', row_html, flags=re.I)]
        if len(cells) < 6 or not re.fullmatch(r'\d{6}', cells[2]):
            continue
        rows.append({
            'companyName': cells[1],
            'stockCode': cells[2],
            'disclosureDate': normalize_kind_date(cells[3]),
            'designationDate': normalize_kind_date(cells[4]),
            'releaseDate': None if cells[5] == '-' else normalize_kind_date(cells[5]),
        })
    return rows


def parse_kind_current_trading_halt_status(html: str) -> dict:
    if is_kind_empty_result(html):
        return {'status': 'not_halted', 'reason': None}

    parsed_body_row = False
    for row_html in re.findall(r'<tr\b[^>]*>([\s\S]*?)</tr>', html, flags=re.I):
        if re.search(r'<th\b', row_html, flags=re.I):
            continue
        cells = [clean_html_cell(match) for match in re.findall(r'<td\b[^>]*>([\s\S]*?)</td>', row_html, flags=re.I)]
        if cells:
            parsed_body_row = True
        if len(cells) == 3:
            return {'status': 'halted', 'reason': cells[2] or None}

    if parsed_body_row:
        raise InvestmentWarningStatusError('KIND 매매거래정지 응답을 해석할 수 없습니다.', 'PARSE')
    return {'status': 'not_halted', 'reason': None}


def parse_kind_disclosure_search_results(html: str) -> list[dict]:
    disclosures = []
    pattern = re.compile(
        r"openDisclsViewer\('([^']+)'\s*,\s*'[^']*'\)[^>]*title=([\"'])(.*?)\2[^>]*>([\s\S]*?)</a>",
        flags=re.I,
    )
    for match in pattern.finditer(html):
        acpt_no = match.group(1).strip()
        title = clean_html_cell(match.group(4) or match.group(3))
        if acpt_no.isdigit() and title:
            disclosures.append({'acptNo': acpt_no, 'title': title})
    return disclosures


def parse_kind_disclosure_viewer_doc_no(html: str) -> str | None:
    selected = re.search(r'<option\b[^>]*value=["\'](\d+)\|[YN]["\'][^>]*selected[^>]*>', html, flags=re.I)
    if selected:
        return selected.group(1)
    first = re.search(r'<option\b[^>]*value=["\'](\d+)\|[YN]["\'][^>]*>\s*투자경고종목지정', html, flags=re.I)
    return first.group(1) if first else None


def parse_kind_disclosure_document_url(html: str) -> str | None:
    match = re.search(r"parent\.setPath\(\s*'[^']*'\s*,\s*'([^']+)'", html, flags=re.I)
    raw_url = unescape(match.group(1)) if match else ''
    if not raw_url:
        return None
    return urllib.parse.urljoin(KIND_DISCLOSURE_VIEWER_URL, raw_url)


def parse_naver_daily_close_prices(text: str) -> list[dict]:
    prices = []
    row_pattern = re.compile(r"\[\s*[\"']?(\d{4}(?:[.-]?\d{2}[.-]?\d{2}))[\"']?\s*,([^\]]+)\]")
    for row_match in row_pattern.finditer(text):
        raw_date = row_match.group(1)
        numeric_values = [
            float(value.replace(',', ''))
            for value in re.findall(r'-?[\d,]+(?:\.\d+)?', row_match.group(2))
        ]
        if not numeric_values:
            continue
        close = numeric_values[0] if ('.' in raw_date or '-' in raw_date) else (
            numeric_values[3] if len(numeric_values) > 3 else float('nan')
        )
        if close <= 0:
            continue
        prices.append({'date': normalize_naver_price_date(raw_date), 'close': clean_number(close)})
    return sorted(prices, key=lambda item: item['date'])


def extract_kind_document_text(html: str) -> str:
    text = unescape(
        re.sub(
            r'<[^>]*>',
            ' ',
            re.sub(r'<br\b[^>]*>', '\n', re.sub(r'<!--[\s\S]*?-->', ' ', html), flags=re.I),
        )
    )
    text = text.replace(' ', ' ')
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r'\s*\n\s*', '\n', text)
    return re.sub(r'\n+', '\n', text).strip()


def normalize_kind_date(value: str) -> str:
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return value
    raise InvestmentWarningStatusError(f'KIND 날짜 형식이 올바르지 않습니다: {value}', 'PARSE')


def normalize_disclosure_title(value: str) -> str:
    return re.sub(r'\s+', '', value)


def clean_html_cell(value: str) -> str:
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]*>', '', value))).strip()


def is_kind_empty_result(html: str) -> bool:
    return '조회된 결과값이 없습니다' in html or re.search(r'colspan=["\']?\d+', html, flags=re.I) is not None


def _url_with_params(base_url: str, params: dict[str, str]) -> str:
    return f'{base_url}?{urllib.parse.urlencode(params)}'


def clean_number(value: float | int) -> float | int:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
