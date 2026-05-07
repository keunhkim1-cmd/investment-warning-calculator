"""Release-criteria computation for investment-warning status.

Pure logic that turns a designation row + KIND disclosure HTML into the
release criteria (threshold rates, judgment dates, basis dates) and turns a
criteria + price series into release-condition rows. No HTTP. No orchestration.
"""
from __future__ import annotations

from datetime import date
import re

from lib.investment_warning_dates import (
    add_krx_trading_day_offset,
    count_krx_trading_day_offset,
    add_krx_trading_days,
    subtract_krx_trading_days,
)
from lib.investment_warning_rows import clean_number, extract_kind_document_text

STANDARD_RELEASE_RATES = {'fiveDay': 0.6, 'fifteenDay': 1.0}


def parse_kind_investment_warning_release_criteria(
    html: str,
    *,
    designation_date: str,
    disclosure_url: str | None = None,
) -> dict | None:
    text = extract_kind_document_text(html)
    five_day_threshold_rate = parse_release_threshold_rate(text, 5)
    fifteen_day_threshold_rate = parse_release_threshold_rate(text, 15)
    first_judgment_month_day = parse_first_judgment_month_day(text)
    basis_month_days = parse_release_basis_month_days(text)

    if (
        five_day_threshold_rate is None
        or fifteen_day_threshold_rate is None
        or first_judgment_month_day is None
        or basis_month_days is None
    ):
        return None

    first_judgment_date = infer_month_day_on_or_after(
        first_judgment_month_day['month'],
        first_judgment_month_day['day'],
        designation_date,
    )
    if not first_judgment_date:
        return None

    t_minus_five_date = infer_month_day_on_or_before(
        basis_month_days['tMinusFive']['month'],
        basis_month_days['tMinusFive']['day'],
        first_judgment_date,
    )
    t_minus_fifteen_date = infer_month_day_on_or_before(
        basis_month_days['tMinusFifteen']['month'],
        basis_month_days['tMinusFifteen']['day'],
        first_judgment_date,
    )
    if not t_minus_five_date or not t_minus_fifteen_date:
        return None

    return {
        'source': 'kind_disclosure',
        'fiveDayThresholdRate': five_day_threshold_rate,
        'fifteenDayThresholdRate': fifteen_day_threshold_rate,
        'firstJudgmentDate': first_judgment_date,
        'tMinusFiveDate': t_minus_five_date,
        'tMinusFifteenDate': t_minus_fifteen_date,
        'disclosureUrl': disclosure_url,
        'fallbackReason': None,
    }


def parse_release_threshold_rate(text: str, day_count: int) -> float | None:
    compact_text = re.sub(r'\s+', ' ', text)
    pattern = re.compile(
        rf'판단일\s*\(\s*T\s*\)[\s\S]{{0,100}}?{day_count}\s*일\s*전날\s*\(\s*T\s*-\s*{day_count}\s*\)[\s\S]{{0,100}}?(\d+(?:\.\d+)?)\s*%\s*이상\s*상승'
    )
    match = pattern.search(compact_text)
    return float(match.group(1)) / 100 if match else None


def parse_first_judgment_month_day(text: str) -> dict | None:
    match = re.search(r'최초\s*판단일은\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', re.sub(r'\s+', ' ', text))
    return {'month': int(match.group(1)), 'day': int(match.group(2))} if match else None


def parse_release_basis_month_days(text: str) -> dict | None:
    match = re.search(
        r'5\s*일\s*전날(?:\s*\([^)]*\))?\s*및\s*15\s*일\s*전날(?:\s*\([^)]*\))?\s*은\s*각각\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*및\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일',
        re.sub(r'\s+', ' ', text),
    )
    if not match:
        return None
    return {
        'tMinusFive': {'month': int(match.group(1)), 'day': int(match.group(2))},
        'tMinusFifteen': {'month': int(match.group(3)), 'day': int(match.group(4))},
    }


def infer_month_day_on_or_after(month: int, day: int, min_date: str) -> str | None:
    min_year = int(min_date[:4])
    same_year = create_iso_month_day(min_year, month, day)
    if same_year is None:
        return None
    if same_year >= min_date:
        return same_year
    return create_iso_month_day(min_year + 1, month, day)


def infer_month_day_on_or_before(month: int, day: int, max_date: str) -> str | None:
    max_year = int(max_date[:4])
    same_year = create_iso_month_day(max_year, month, day)
    if same_year is None:
        return None
    if same_year <= max_date:
        return same_year
    return create_iso_month_day(max_year - 1, month, day)


def create_iso_month_day(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def create_fallback_release_criteria(
    warning_row: dict,
    fallback_reason: str,
    disclosure_url: str | None = None,
) -> dict:
    first_judgment_date = add_krx_trading_days(warning_row['designationDate'], 10)
    return {
        'source': 'fallback',
        'fiveDayThresholdRate': STANDARD_RELEASE_RATES['fiveDay'],
        'fifteenDayThresholdRate': STANDARD_RELEASE_RATES['fifteenDay'],
        'firstJudgmentDate': first_judgment_date,
        'tMinusFiveDate': subtract_krx_trading_days(first_judgment_date, 5),
        'tMinusFifteenDate': subtract_krx_trading_days(first_judgment_date, 15),
        'disclosureUrl': disclosure_url,
        'fallbackReason': fallback_reason,
    }


def resolve_release_basis_dates(judgment_date: str, release_criteria: dict) -> dict:
    offset = count_krx_trading_day_offset(release_criteria['firstJudgmentDate'], judgment_date)
    return {
        'fiveDayBasisDate': add_krx_trading_day_offset(release_criteria['tMinusFiveDate'], offset),
        'fifteenDayBasisDate': add_krx_trading_day_offset(release_criteria['tMinusFifteenDate'], offset),
    }


def create_investment_warning_calculation_basis(trading_halt_status: dict, release_criteria: dict) -> str:
    if trading_halt_status['status'] == 'halted':
        return '현재 매매거래정지 상태라 해제 가능일 산정을 보류합니다.'
    if trading_halt_status['status'] == 'unknown':
        return '매매거래정지 상태를 확인할 수 없어 해제 가능일 산정을 보류합니다.'
    if release_criteria['source'] == 'kind_disclosure':
        return 'KIND 지정 공시 원문 해제요건 기준입니다.'
    return f"KIND 지정 공시 해제요건 파싱 실패로 기본 기준을 사용했습니다. 사유: {release_criteria.get('fallbackReason', '')}"


def create_future_judgment_release_conditions(
    basis_dates: dict,
    release_criteria: dict,
    judgment_date: str,
) -> list[dict]:
    return [
        create_unavailable_release_condition(
            'five_day_gain',
            basis_date=basis_dates['fiveDayBasisDate'],
            threshold_rate=release_criteria['fiveDayThresholdRate'],
            evaluation_date=judgment_date,
            status_reason='future_judgment_date',
        ),
        create_unavailable_release_condition(
            'fifteen_day_gain',
            basis_date=basis_dates['fifteenDayBasisDate'],
            threshold_rate=release_criteria['fifteenDayThresholdRate'],
            evaluation_date=judgment_date,
            status_reason='future_judgment_date',
        ),
        create_unavailable_release_condition(
            'fifteen_day_high',
            evaluation_date=judgment_date,
            status_reason='future_judgment_date',
        ),
    ]


def create_rate_release_condition(
    condition_type: str,
    basis_date: str,
    basis_price: int | float | None,
    evaluation: dict | None,
    threshold_rate: float,
    status_reason: str | None = None,
) -> dict:
    threshold_price = None if basis_price is None else clean_number(round(basis_price * (1 + threshold_rate), 2))
    status = 'unavailable'
    if threshold_price is not None and evaluation is not None and evaluation.get('close', 0) > 0:
        status = 'exceeded' if evaluation['close'] >= threshold_price else 'safe'
    condition = {
        'type': condition_type,
        'status': status,
        'basisDate': basis_date,
        'basisPrice': basis_price,
        'thresholdRate': threshold_rate,
        'thresholdPrice': threshold_price,
        'evaluationDate': evaluation['date'] if evaluation else None,
        'evaluationPrice': evaluation['close'] if evaluation else None,
    }
    if status == 'unavailable':
        condition['statusReason'] = status_reason or infer_unavailable_status_reason(
            basis_price,
            evaluation,
        )
    return condition


def create_high_release_condition(
    basis_date: str | None,
    basis_price: int | float | None,
    evaluation: dict | None,
    status_reason: str | None = None,
) -> dict:
    threshold_price = basis_price
    status = 'unavailable'
    if threshold_price is not None and evaluation is not None and evaluation.get('close', 0) > 0:
        status = 'exceeded' if evaluation['close'] >= threshold_price else 'safe'
    condition = {
        'type': 'fifteen_day_high',
        'status': status,
        'basisDate': basis_date,
        'basisPrice': basis_price,
        'thresholdRate': None,
        'thresholdPrice': threshold_price,
        'evaluationDate': evaluation['date'] if evaluation else None,
        'evaluationPrice': evaluation['close'] if evaluation else None,
    }
    if status == 'unavailable':
        condition['statusReason'] = status_reason or infer_unavailable_status_reason(
            basis_price,
            evaluation,
        )
    return condition


def infer_unavailable_status_reason(
    basis_price: int | float | None,
    evaluation: dict | None,
) -> str:
    if evaluation is None or evaluation.get('close', 0) <= 0:
        return 'missing_evaluation_price'
    if basis_price is None:
        return 'missing_basis_price'
    return 'missing_evaluation_price'


def create_unavailable_release_conditions() -> list[dict]:
    return [
        create_unavailable_release_condition('five_day_gain'),
        create_unavailable_release_condition('fifteen_day_gain'),
        create_unavailable_release_condition('fifteen_day_high'),
    ]


def create_unavailable_release_condition(
    condition_type: str,
    *,
    basis_date: str | None = None,
    threshold_rate: float | None = None,
    evaluation_date: str | None = None,
    status_reason: str | None = None,
) -> dict:
    condition = {
        'type': condition_type,
        'status': 'unavailable',
        'basisDate': basis_date,
        'basisPrice': None,
        'thresholdRate': threshold_rate,
        'thresholdPrice': None,
        'evaluationDate': evaluation_date,
        'evaluationPrice': None,
    }
    if status_reason:
        condition['statusReason'] = status_reason
    return condition


def find_close_price(prices: list[dict], price_date: str) -> dict | None:
    return next((price for price in prices if price['date'] == price_date), None)


def find_latest_price_on_or_before(prices: list[dict], price_date: str) -> dict | None:
    eligible = [price for price in prices if price['date'] <= price_date]
    return sorted(eligible, key=lambda item: item['date'], reverse=True)[0] if eligible else None


def find_prior_recent_high(prices: list[dict], start_date: str, judgment_date: str) -> dict | None:
    prior_prices = [price for price in prices if start_date <= price['date'] < judgment_date]
    if len(prior_prices) < 14:
        return None
    return max(prior_prices, key=lambda item: item['close'])


def find_recent_high_through(prices: list[dict], start_date: str, evaluation_date: str) -> dict | None:
    window_prices = [price for price in prices if start_date <= price['date'] <= evaluation_date]
    return max(window_prices, key=lambda item: item['close']) if window_prices else None
