"""DART corporation registry shared by stock-code mapping and allowlists."""

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from lib.cache import TTLCache
from lib.dart_base import fetch_bytes
from lib.http_utils import log_event, safe_exception_text
from lib.timeouts import DART_DOCUMENT_TIMEOUT


CORP_CODE_RE = re.compile(r'^\d{8}$')
STOCK_CODE_RE = re.compile(r'^\d{6}$')
DART_REGISTRY_CACHE_KEY = 'dart:corp-registry:v1'
DART_REGISTRY_TTL_SECONDS = 35 * 24 * 3600
ROOT = Path(__file__).resolve().parent.parent
PACKAGED_CORP_PATH = ROOT / 'data' / 'dart-corps.json'

_registry_cache = TTLCache(ttl=24 * 3600, name='dart-corp-registry')


def _normalize_row(corp_code: object, corp_name: object, stock_code: object) -> dict | None:
    corp_code = str(corp_code or '').strip()
    corp_name = str(corp_name or '').strip()
    stock_code = str(stock_code or '').strip()
    if not stock_code or not corp_code:
        return None
    return {'c': corp_code, 'n': corp_name, 's': stock_code}


def _parse_packaged_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        normalized = _normalize_row(row.get('c'), row.get('n'), row.get('s'))
        if normalized:
            out.append(normalized)
    return out


def load_packaged_corp_rows() -> list[dict]:
    """Load the bundled fallback registry from the repository."""
    with PACKAGED_CORP_PATH.open(encoding='utf-8') as f:
        return _parse_packaged_rows(json.load(f))


def parse_corp_code_zip(raw: bytes) -> list[dict]:
    """Parse DART corpCode.xml zip bytes into compact registry rows."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open('CORPCODE.xml') as f:
            xml_data = f.read()

    root = ET.fromstring(xml_data)
    rows = []
    for item in root.iter('list'):
        normalized = _normalize_row(
            item.findtext('corp_code'),
            item.findtext('corp_name'),
            item.findtext('stock_code'),
        )
        if normalized:
            rows.append(normalized)
    return rows


def fetch_live_corp_rows() -> list[dict]:
    """Fetch the latest listed-company registry from DART."""
    raw = fetch_bytes('corpCode.xml', timeout=DART_DOCUMENT_TIMEOUT, retries=1)
    return parse_corp_code_zip(raw)


def validate_corp_rows(rows: list[dict]) -> None:
    """Validate a compact DART registry before using or storing it."""
    if not rows:
        raise RuntimeError('DART corp registry is empty.')

    seen = set()
    for row in rows:
        corp_code = str(row.get('c', '') or '').strip()
        stock_code = str(row.get('s', '') or '').strip()
        if not CORP_CODE_RE.fullmatch(corp_code):
            raise RuntimeError(f'invalid corp_code: {corp_code!r}')
        if not stock_code:
            raise RuntimeError(f'missing stock_code for corp_code={corp_code}')
        key = (corp_code, stock_code)
        if key in seen:
            raise RuntimeError(f'duplicate corp/stock pair: {key!r}')
        seen.add(key)


def _load_durable_corp_rows() -> list[dict] | None:
    try:
        from lib.durable_cache import get_json
        payload = get_json(DART_REGISTRY_CACHE_KEY)
    except Exception as e:
        log_event('warning', 'dart_registry_durable_read_failed',
                  error=safe_exception_text(e))
        return None

    if not isinstance(payload, dict):
        return None
    raw_rows = payload.get('rows')
    if not isinstance(raw_rows, list):
        return None

    rows = _parse_packaged_rows(raw_rows)
    try:
        validate_corp_rows(rows)
    except Exception as e:
        log_event('warning', 'dart_registry_durable_invalid',
                  error=safe_exception_text(e))
        return None
    return rows


def refresh_durable_corp_rows() -> dict:
    """Fetch DART corpCode.xml and store the compact registry in Upstash."""
    rows = fetch_live_corp_rows()
    validate_corp_rows(rows)
    updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    payload = {
        'updatedAt': updated_at,
        'rows': rows,
    }

    stored = False
    try:
        from lib.durable_cache import enabled as durable_cache_enabled, set_json
        if durable_cache_enabled():
            set_json(DART_REGISTRY_CACHE_KEY, payload, ttl=DART_REGISTRY_TTL_SECONDS)
            stored = True
    finally:
        _registry_cache.clear()

    log_event('info', 'dart_registry_refresh_completed',
              rows=len(rows), stored=stored, updated_at=updated_at)
    return {
        'rows': len(rows),
        'updatedAt': updated_at,
        'stored': stored,
        'key': DART_REGISTRY_CACHE_KEY,
        'ttlSeconds': DART_REGISTRY_TTL_SECONDS,
    }


def load_corp_rows() -> list[dict]:
    """Return the cached DART registry, falling back to the bundled snapshot."""

    def _fetch():
        rows = _load_durable_corp_rows()
        if rows:
            return rows
        return load_packaged_corp_rows()

    return _registry_cache.get_or_set(
        'rows',
        _fetch,
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


def corp_map_by_stock_code() -> dict:
    """Return {stock_code: {corp_code, corp_name}} using the shared registry."""
    return _registry_cache.get_or_set(
        'stock-map',
        lambda: {
            row['s']: {'corp_code': row['c'], 'corp_name': row['n']}
            for row in load_corp_rows()
            if row.get('s')
        },
        allow_stale_on_error=True,
        max_stale=7 * 24 * 3600,
    )


def resolve_exact_stock_codes(query: str) -> list[dict]:
    """Resolve a 6-digit stock code or exact DART corp_name to stock-code items."""
    value = (query or '').strip()
    if STOCK_CODE_RE.fullmatch(value):
        return [{'code': value, 'name': '', 'corpCode': ''}]
    if not value:
        return []

    value_key = value.casefold()
    matches = []
    seen_codes = set()
    for row in load_corp_rows():
        corp_name = str(row.get('n', '') or '').strip()
        stock_code = str(row.get('s', '') or '').strip()
        if corp_name.casefold() != value_key or not STOCK_CODE_RE.fullmatch(stock_code):
            continue
        if stock_code in seen_codes:
            continue
        seen_codes.add(stock_code)
        matches.append({
            'code': stock_code,
            'name': corp_name,
            'corpCode': row.get('c', ''),
        })
    return matches
