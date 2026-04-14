"""DART Open API — 공시 검색 & 재무제표 조회"""
import urllib.request, urllib.parse, json, os

DART_API_KEY = os.environ.get('DART_API_KEY', '')
DART_BASE = 'https://opendart.fss.or.kr/api'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def fetch_financial(corp_code: str, bsns_year: str, reprt_code: str = '11011') -> dict:
    """재무제표 주요계정 조회. reprt_code: 11011=사업보고서, 11014=반기, 11012=1분기, 11013=3분기"""
    params = urllib.parse.urlencode({
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': bsns_year,
        'reprt_code': reprt_code,
    })
    url = f'{DART_BASE}/fnlttSinglAcnt.json?{params}'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def search_disclosure(corp_code: str = '', bgn_de: str = '', end_de: str = '',
                      page_no: int = 1, page_count: int = 20,
                      pblntf_ty: str = '') -> dict:
    """공시 목록 검색 (corp_code 기반)"""
    params = {
        'crtfc_key': DART_API_KEY,
        'page_no': str(page_no),
        'page_count': str(page_count),
    }
    if corp_code:
        params['corp_code'] = corp_code
    if bgn_de:
        params['bgn_de'] = bgn_de
    if end_de:
        params['end_de'] = end_de
    if pblntf_ty:
        params['pblntf_ty'] = pblntf_ty

    url = f'{DART_BASE}/list.json?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))
