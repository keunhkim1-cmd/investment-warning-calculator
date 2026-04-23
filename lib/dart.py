"""DART Open API — 공시 검색 & 재무제표 조회"""
import urllib.request, json, os

from lib.retry import retry
from lib.http_utils import build_url, urlopen_sanitized

DART_BASE = 'https://opendart.fss.or.kr/api'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
DART_SECRET_PARAMS = ('crtfc_key',)


def _get_api_key() -> str:
    key = os.environ.get('DART_API_KEY', '').strip()
    if not key:
        raise ValueError('DART_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def search_disclosure(corp_code: str = '', bgn_de: str = '', end_de: str = '',
                      page_no: int = 1, page_count: int = 20,
                      pblntf_ty: str = '') -> dict:
    """공시 목록 검색 (corp_code 기반)"""
    api_key = _get_api_key()
    params = {
        'crtfc_key': api_key,
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

    request_url = build_url(DART_BASE, 'list.json', params)

    def _call():
        req = urllib.request.Request(request_url, headers=HEADERS)
        with urlopen_sanitized(req, timeout=10, secret_query_keys=DART_SECRET_PARAMS) as r:
            return json.loads(r.read().decode('utf-8'))

    return retry(_call)
