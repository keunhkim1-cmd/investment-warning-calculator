"""DART corp_code 매핑 — 종목코드 → DART 고유번호"""
import urllib.request, io, zipfile, os
from xml.etree import ElementTree as ET

from lib.retry import retry
from lib.cache import TTLCache

DART_BASE = 'https://opendart.fss.or.kr/api'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

# corp_code 매핑은 거의 변하지 않음 — 24시간 캐시
_cache = TTLCache(ttl=24 * 3600)


def _api_key() -> str:
    key = os.environ.get('DART_API_KEY', '')
    if not key:
        raise ValueError('DART_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def _load_corp_map() -> dict:
    """DART corpCode.xml zip 다운로드 → {stock_code: {corp_code, corp_name}} 매핑."""
    cached = _cache.get('corp_map')
    if cached is not None:
        return cached

    url = f'{DART_BASE}/corpCode.xml?crtfc_key={_api_key()}'

    def _call():
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    raw = retry(_call)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open('CORPCODE.xml') as f:
            xml_data = f.read()

    root = ET.fromstring(xml_data)
    mapping = {}
    for item in root.iter('list'):
        stock = (item.findtext('stock_code') or '').strip()
        if not stock:
            continue
        mapping[stock] = {
            'corp_code': (item.findtext('corp_code') or '').strip(),
            'corp_name': (item.findtext('corp_name') or '').strip(),
        }

    _cache.set('corp_map', mapping)
    return mapping


def find_corp_by_stock_code(stock_code: str) -> dict | None:
    """종목코드(6자리) → {'corp_code': ..., 'corp_name': ...} 또는 None."""
    return _load_corp_map().get(stock_code)
