"""DART corp_code 매핑 — 종목코드 → DART 고유번호"""
from lib.dart_registry import corp_map_by_stock_code, resolve_exact_stock_codes


def find_corp_by_stock_code(stock_code: str) -> dict | None:
    """종목코드(6자리) → {'corp_code': ..., 'corp_name': ...} 또는 None."""
    return corp_map_by_stock_code().get(stock_code)


def find_stock_codes_by_exact_name(name: str) -> list[dict]:
    """정확한 DART 종목명 또는 6자리 종목코드 → 종목코드 후보 목록."""
    return resolve_exact_stock_codes(name)
