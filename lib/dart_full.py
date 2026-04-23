"""DART 전체 재무제표 (fnlttSinglAcntAll) 어댑터"""
import urllib.request, json, os

from lib.retry import retry
from lib.cache import TTLCache
from lib.http_utils import build_url, urlopen_sanitized

DART_BASE = 'https://opendart.fss.or.kr/api'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
DART_SECRET_PARAMS = ('crtfc_key',)

# 6시간 캐시 — 사업보고서는 자주 바뀌지 않음
_cache = TTLCache(ttl=6 * 3600)


def _api_key() -> str:
    key = os.environ.get('DART_API_KEY', '').strip()
    if not key:
        raise ValueError('DART_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def fetch_all(corp_code: str, bsns_year: str, reprt_code: str, fs_div: str = 'CFS') -> dict:
    """전체 재무제표 조회.
    reprt_code: 11011=사업보고서, 11014=반기, 11012=1Q, 11013=3Q
    fs_div: CFS=연결, OFS=별도
    """
    key = f'all:{corp_code}:{bsns_year}:{reprt_code}:{fs_div}'
    cached = _cache.get(key)
    if cached is not None:
        return cached

    params = {
        'crtfc_key': _api_key(),
        'corp_code': corp_code,
        'bsns_year': bsns_year,
        'reprt_code': reprt_code,
        'fs_div': fs_div,
    }
    request_url = build_url(DART_BASE, 'fnlttSinglAcntAll.json', params)

    def _call():
        req = urllib.request.Request(request_url, headers=HEADERS)
        with urlopen_sanitized(req, timeout=15, secret_query_keys=DART_SECRET_PARAMS) as r:
            return json.loads(r.read().decode('utf-8'))

    data = retry(_call)
    _cache.set(key, data)
    return data
