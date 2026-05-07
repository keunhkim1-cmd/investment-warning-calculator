"""Date math for investment-warning judgment-date calculations.

Pure functions: KST-day coercion, ISO-date parsing, KRX trading-day arithmetic,
and Naver price-date normalization. Higher-level orchestration lives in the
``lib.investment_warning_status`` facade.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re

from lib.holidays import MAX_HOLIDAY_YEAR, is_trading_day
from lib.investment_warning_errors import InvestmentWarningStatusError

KST = timezone(timedelta(hours=9))


def format_kst_date(now: datetime | date | None = None) -> str:
    return _coerce_kst_date(now).isoformat()


def format_kst_date_years_before(now: datetime | date | None, years: int) -> str:
    day = _coerce_kst_date(now)
    try:
        return day.replace(year=day.year - years).isoformat()
    except ValueError:
        return day.replace(year=day.year - years, day=28).isoformat()


def _coerce_kst_date(now: datetime | date | None = None) -> date:
    if now is None:
        return datetime.now(KST).date()
    if isinstance(now, datetime):
        if now.tzinfo is None:
            return now.date()
        return now.astimezone(KST).date()
    return now


def add_krx_trading_days(start_date: str, trading_day_count: int) -> str:
    if trading_day_count < 1:
        raise ValueError('trading_day_count must be a positive integer.')
    current = parse_iso_date(start_date)
    counted = 0
    while True:
        if _is_supported_trading_day(current):
            counted += 1
        if counted == trading_day_count:
            return current.isoformat()
        current += timedelta(days=1)


def next_krx_trading_day(day: str) -> str:
    current = parse_iso_date(day) + timedelta(days=1)
    while not _is_supported_trading_day(current):
        current += timedelta(days=1)
    return current.isoformat()


def subtract_krx_trading_days(day: str, trading_day_count: int) -> str:
    if trading_day_count < 1:
        raise ValueError('trading_day_count must be a positive integer.')
    current = parse_iso_date(day)
    counted = 0
    while True:
        current -= timedelta(days=1)
        if _is_supported_trading_day(current):
            counted += 1
        if counted == trading_day_count:
            return current.isoformat()


def krx_trading_day_on_or_after(day: str) -> str:
    current = parse_iso_date(day)
    while not _is_supported_trading_day(current):
        current += timedelta(days=1)
    return current.isoformat()


def count_krx_trading_day_offset(start_date: str, end_date: str) -> int:
    if end_date <= start_date:
        return 0
    current = start_date
    offset = 0
    while current < end_date:
        current = next_krx_trading_day(current)
        offset += 1
    return offset


def add_krx_trading_day_offset(start_date: str, offset: int) -> str:
    current = start_date
    for _ in range(offset):
        current = next_krx_trading_day(current)
    return current


def _is_supported_trading_day(day: date) -> bool:
    if day.year > MAX_HOLIDAY_YEAR:
        raise InvestmentWarningStatusError(f'공휴일 데이터가 {MAX_HOLIDAY_YEAR}년까지만 있습니다.', 'CALENDAR_RANGE')
    return is_trading_day(day)


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvestmentWarningStatusError(f'날짜 형식이 올바르지 않습니다: {value}', 'PARSE') from exc


def normalize_naver_price_date(value: str) -> str:
    if re.fullmatch(r'\d{8}', value):
        return f'{value[:4]}-{value[4:6]}-{value[6:8]}'
    return value.replace('.', '-')


def to_compact_date(value: str) -> str:
    return value.replace('-', '')
