"""Investment-warning status and release forecast logic.

This module mirrors the totem-bot KRX/KIND implementation in Python so web,
API, and Telegram callers use one server-side source of truth.

Top-level orchestration lives here. Domain primitives are split into
``investment_warning_dates``, ``investment_warning_rows``, and
``investment_warning_release`` and re-exported below to preserve the original
public attribute surface (``iws.<name>`` access patterns used by tests).
"""
from __future__ import annotations

from datetime import date, datetime
import re

from lib.cache import TTLCache

# Re-exports preserve the original ``iws.<name>`` attribute surface used by tests.
from lib.investment_warning_dates import (  # noqa: F401
    KST,
    _coerce_kst_date,
    _is_supported_trading_day,
    add_krx_trading_day_offset,
    add_krx_trading_days,
    count_krx_trading_day_offset,
    format_kst_date,
    format_kst_date_years_before,
    krx_trading_day_on_or_after,
    next_krx_trading_day,
    normalize_naver_price_date,
    parse_iso_date,
    subtract_krx_trading_days,
    to_compact_date,
)
from lib.investment_warning_errors import InvestmentWarningStatusError  # noqa: F401
from lib.investment_warning_release import (  # noqa: F401
    STANDARD_RELEASE_RATES,
    create_fallback_release_criteria,
    create_future_judgment_release_conditions,
    create_high_release_condition,
    create_investment_warning_calculation_basis,
    create_iso_month_day,
    create_rate_release_condition,
    create_unavailable_release_condition,
    create_unavailable_release_conditions,
    find_close_price,
    find_latest_price_on_or_before,
    find_prior_recent_high,
    find_recent_high_through,
    infer_month_day_on_or_after,
    infer_month_day_on_or_before,
    infer_unavailable_status_reason,
    parse_first_judgment_month_day,
    parse_kind_investment_warning_release_criteria,
    parse_release_basis_month_days,
    parse_release_threshold_rate,
    resolve_release_basis_dates,
)
from lib.investment_warning_rows import (  # noqa: F401
    KIND_DISCLOSURE_DETAILS_URL,
    KIND_DISCLOSURE_VIEWER_URL,
    KIND_HEADERS,
    KIND_INVEST_WARNING_LOOKBACK_YEARS,
    KIND_INVEST_WARNING_URL,
    KIND_POST_HEADERS,
    KIND_TRADING_HALT_MARKET_TYPES,
    KIND_TRADING_HALT_URL,
    NAVER_DAILY_PRICE_URL,
    NAVER_HEADERS,
    _url_with_params,
    _utc_now_iso,
    clean_html_cell,
    clean_number,
    decode_kind_text,
    extract_charset,
    extract_kind_document_text,
    fetch_current_trading_halt_status,
    fetch_daily_close_prices,
    fetch_investment_warning_designation_disclosure,
    fetch_investment_warning_designation_disclosure_reference,
    fetch_investment_warning_rows,
    is_euc_kr_charset,
    is_kind_empty_result,
    kind_get_text,
    kind_post_text,
    normalize_disclosure_title,
    normalize_kind_date,
    parse_kind_current_trading_halt_status,
    parse_kind_disclosure_document_url,
    parse_kind_disclosure_search_results,
    parse_kind_disclosure_viewer_doc_no,
    parse_kind_investment_warning_rows,
    parse_naver_daily_close_prices,
)

KIND_INVEST_WARNING_SOURCE_URL = (
    'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do?method=investattentwarnriskyMain'
)

_status_cache = TTLCache(ttl=10 * 60, name='investment-warning-status', durable=True)


def get_investment_warning_status(stock_code: str, now: datetime | date | None = None) -> dict:
    normalized_stock_code = (stock_code or '').strip()
    if not re.fullmatch(r'\d{6}', normalized_stock_code):
        raise ValueError('stockCode는 6자리 종목코드여야 합니다.')

    if now is not None:
        return _build_investment_warning_status(normalized_stock_code, now)

    cache_key = f'{normalized_stock_code}:{format_kst_date()}'
    return _status_cache.get_or_set(
        cache_key,
        lambda: _build_investment_warning_status(normalized_stock_code, None),
        allow_stale_on_error=True,
        max_stale=6 * 3600,
    )


def _build_investment_warning_status(
    normalized_stock_code: str,
    now: datetime | date | None = None,
) -> dict:
    fetched_at = _utc_now_iso()
    rows = fetch_investment_warning_rows(normalized_stock_code, now)
    active_rows = [
        row for row in rows
        if row.get('stockCode') == normalized_stock_code and row.get('releaseDate') is None
    ]
    active_rows.sort(key=lambda row: row.get('designationDate', ''), reverse=True)
    warning_row = active_rows[0] if active_rows else None

    if not warning_row:
        return {
            'status': 'not_warning',
            'stockCode': normalized_stock_code,
            'fetchedAt': fetched_at,
        }

    trading_halt_status = fetch_current_trading_halt_status(normalized_stock_code)
    release_criteria = resolve_investment_warning_release_criteria(warning_row)
    first_judgment_date = release_criteria['firstJudgmentDate']
    if trading_halt_status['status'] != 'not_halted':
        next_judgment_date = None
    else:
        next_judgment_date = resolve_next_investment_warning_judgment_date(
            first_judgment_date,
            now,
        )
    expected_release_date = next_krx_trading_day(next_judgment_date) if next_judgment_date else None
    release_conditions = resolve_investment_warning_release_conditions(
        normalized_stock_code,
        next_judgment_date,
        now,
        release_criteria,
    )

    return {
        'status': 'investment_warning',
        'stockCode': normalized_stock_code,
        'companyName': warning_row['companyName'],
        'disclosureDate': warning_row['disclosureDate'],
        'designationDate': warning_row['designationDate'],
        'firstJudgmentDate': first_judgment_date,
        'nextJudgmentDate': next_judgment_date,
        'expectedReleaseDate': expected_release_date,
        'releaseConditions': release_conditions,
        'releaseCriteria': release_criteria,
        'calculationBasis': create_investment_warning_calculation_basis(
            trading_halt_status,
            release_criteria,
        ),
        'tradingHaltReason': trading_halt_status.get('reason'),
        'sourceUrl': KIND_INVEST_WARNING_SOURCE_URL,
        'fetchedAt': fetched_at,
    }


def resolve_investment_warning_release_criteria(warning_row: dict) -> dict:
    disclosure_url = None
    try:
        disclosure = fetch_investment_warning_designation_disclosure(warning_row)
        disclosure_url = disclosure['url']
        criteria = parse_kind_investment_warning_release_criteria(
            disclosure['html'],
            designation_date=warning_row['designationDate'],
            disclosure_url=disclosure_url,
        )
        if not criteria:
            raise InvestmentWarningStatusError('KIND 지정 공시의 해제요건을 해석할 수 없습니다.', 'PARSE')
        return criteria
    except Exception as exc:
        return create_fallback_release_criteria(warning_row, str(exc) or '알 수 없는 오류', disclosure_url)


def resolve_investment_warning_release_conditions(
    stock_code: str,
    judgment_date: str | None,
    now: datetime | date | None,
    release_criteria: dict,
) -> list[dict]:
    if not judgment_date:
        return create_unavailable_release_conditions()

    today = format_kst_date(now)

    try:
        if today < judgment_date:
            return resolve_current_preview_release_conditions(
                stock_code,
                today,
                release_criteria,
            )

        basis_dates = resolve_release_basis_dates(judgment_date, release_criteria)
        recent_high_start_date = subtract_krx_trading_days(judgment_date, 14)
        prices = fetch_daily_close_prices(
            stock_code,
            min(basis_dates['fifteenDayBasisDate'], recent_high_start_date),
            judgment_date,
        )
        evaluation = find_close_price(prices, judgment_date)
        five_day_basis = find_close_price(prices, basis_dates['fiveDayBasisDate'])
        fifteen_day_basis = find_close_price(prices, basis_dates['fifteenDayBasisDate'])
        recent_high = find_prior_recent_high(prices, recent_high_start_date, judgment_date)
        return [
            create_rate_release_condition(
                'five_day_gain',
                basis_dates['fiveDayBasisDate'],
                five_day_basis['close'] if five_day_basis else None,
                evaluation,
                release_criteria['fiveDayThresholdRate'],
            ),
            create_rate_release_condition(
                'fifteen_day_gain',
                basis_dates['fifteenDayBasisDate'],
                fifteen_day_basis['close'] if fifteen_day_basis else None,
                evaluation,
                release_criteria['fifteenDayThresholdRate'],
            ),
            create_high_release_condition(
                recent_high['date'] if recent_high else None,
                recent_high['close'] if recent_high else None,
                evaluation,
            ),
        ]
    except Exception:
        return create_unavailable_release_conditions()


def resolve_current_preview_release_conditions(
    stock_code: str,
    today: str,
    release_criteria: dict,
) -> list[dict]:
    fetch_start_date = subtract_krx_trading_days(today, 20)
    prices = fetch_daily_close_prices(stock_code, fetch_start_date, today)
    evaluation = find_latest_price_on_or_before(prices, today)
    if not evaluation:
        return create_unavailable_release_conditions()

    evaluation_date = evaluation['date']
    basis_dates = {
        'fiveDayBasisDate': subtract_krx_trading_days(evaluation_date, 5),
        'fifteenDayBasisDate': subtract_krx_trading_days(evaluation_date, 15),
    }
    recent_high_start_date = subtract_krx_trading_days(evaluation_date, 14)
    five_day_basis = find_close_price(prices, basis_dates['fiveDayBasisDate'])
    fifteen_day_basis = find_close_price(prices, basis_dates['fifteenDayBasisDate'])
    recent_high = find_recent_high_through(prices, recent_high_start_date, evaluation_date)
    return [
        create_rate_release_condition(
            'five_day_gain',
            basis_dates['fiveDayBasisDate'],
            five_day_basis['close'] if five_day_basis else None,
            evaluation,
            release_criteria['fiveDayThresholdRate'],
        ),
        create_rate_release_condition(
            'fifteen_day_gain',
            basis_dates['fifteenDayBasisDate'],
            fifteen_day_basis['close'] if fifteen_day_basis else None,
            evaluation,
            release_criteria['fifteenDayThresholdRate'],
        ),
        create_high_release_condition(
            recent_high['date'] if recent_high else None,
            recent_high['close'] if recent_high else None,
            evaluation,
        ),
    ]


def resolve_next_investment_warning_judgment_date(first_judgment_date: str, now: datetime | date | None = None) -> str:
    today = format_kst_date(now)
    if today <= first_judgment_date:
        return first_judgment_date
    return krx_trading_day_on_or_after(today)
