"""Shared request input validation helpers."""
import re
from datetime import datetime


STOCK_CODE_RE = re.compile(r'^\d{6}$')
CORP_CODE_RE = re.compile(r'^\d{8}$')
YYYYMMDD_RE = re.compile(r'^\d{8}$')
DART_PBLNTF_TY = frozenset('ABCDEFGHIJ')
CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')


def normalize_query(value: str, label: str = 'name', max_chars: int = 40, max_bytes: int = 160) -> str:
    """Normalize a human stock-name query and reject oversized/control input."""
    raw = (value or '').strip()
    if CONTROL_RE.search(raw):
        raise ValueError(f'{label} 값에 허용되지 않는 문자가 있습니다.')
    text = re.sub(r'\s+', ' ', raw)
    if not text:
        raise ValueError(f'{label} 값이 필요합니다.')
    if len(text) > max_chars or len(text.encode('utf-8')) > max_bytes:
        raise ValueError(f'{label} 값이 너무 깁니다.')
    return text


def validate_stock_code(value: str) -> str:
    code = (value or '').strip()
    if not STOCK_CODE_RE.fullmatch(code):
        raise ValueError('잘못된 종목코드 형식')
    return code


def validate_corp_code(value: str, required: bool = True) -> str:
    code = (value or '').strip()
    if not code:
        if required:
            raise ValueError('corp_code가 필요합니다.')
        return ''
    if not CORP_CODE_RE.fullmatch(code):
        raise ValueError('잘못된 corp_code 형식')
    return code


def parse_int_range(value: str, label: str, default: int, min_value: int, max_value: int) -> int:
    raw = (value or str(default)).strip()
    try:
        parsed = int(raw)
    except ValueError:
        raise ValueError(f'{label} 값은 정수여야 합니다.')
    if parsed < min_value or parsed > max_value:
        raise ValueError(f'{label} 값은 {min_value}~{max_value} 범위여야 합니다.')
    return parsed


def validate_yyyymmdd(value: str, label: str, required: bool = False) -> str:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValueError(f'{label} 값이 필요합니다.')
        return ''
    if not YYYYMMDD_RE.fullmatch(raw):
        raise ValueError(f'{label} 값은 YYYYMMDD 형식이어야 합니다.')
    try:
        datetime.strptime(raw, '%Y%m%d')
    except ValueError:
        raise ValueError(f'{label} 값이 유효한 날짜가 아닙니다.')
    return raw


def validate_date_range(bgn_de: str, end_de: str, max_days: int = 1098) -> tuple[str, str]:
    bgn = validate_yyyymmdd(bgn_de, 'bgn_de')
    end = validate_yyyymmdd(end_de, 'end_de')
    if bgn and end:
        bgn_dt = datetime.strptime(bgn, '%Y%m%d')
        end_dt = datetime.strptime(end, '%Y%m%d')
        if bgn_dt > end_dt:
            raise ValueError('bgn_de는 end_de보다 늦을 수 없습니다.')
        if (end_dt - bgn_dt).days > max_days:
            raise ValueError(f'조회 기간은 최대 {max_days}일입니다.')
    return bgn, end


def validate_dart_pblntf_ty(value: str) -> str:
    raw = (value or '').strip().upper()
    if raw and raw not in DART_PBLNTF_TY:
        raise ValueError('잘못된 공시 유형입니다.')
    return raw
