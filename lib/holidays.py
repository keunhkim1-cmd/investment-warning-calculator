"""한국 공휴일 및 영업일 계산 — data/holidays.json 단일 소스"""
import json, os
from datetime import date, timedelta

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'holidays.json')

with open(_DATA_PATH, encoding='utf-8') as f:
    HOLIDAYS = set(json.load(f))

MAX_HOLIDAY_YEAR = 2029


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.strftime('%Y-%m-%d') not in HOLIDAYS


def add_trading_days(start: date, n: int) -> date:
    if start.year > MAX_HOLIDAY_YEAR:
        raise ValueError(f'공휴일 데이터가 {MAX_HOLIDAY_YEAR}년까지만 있습니다.')
    cur, count = start, 0
    while count < n:
        cur += timedelta(days=1)
        if is_trading_day(cur):
            count += 1
    return cur


def count_trading_days(start: date, end: date) -> int:
    count, cur = 0, start
    while cur <= end:
        if is_trading_day(cur):
            count += 1
        cur += timedelta(days=1)
    return count
