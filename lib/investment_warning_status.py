"""Investment-warning status and release forecast logic.

This module mirrors the totem-bot KRX/KIND implementation in Python so web,
API, and Telegram callers use one server-side source of truth.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import unescape
import re
import urllib.parse

from lib.holidays import MAX_HOLIDAY_YEAR, is_trading_day
from lib.http_client import BROWSER_HEADERS, request_bytes, request_text
from lib.timeouts import KRX_KIND_TIMEOUT, NAVER_PRICE_TIMEOUT

KST = timezone(timedelta(hours=9))

KIND_INVEST_WARNING_URL = 'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do'
KIND_INVEST_WARNING_SOURCE_URL = (
    'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do?method=investattentwarnriskyMain'
)
KIND_DISCLOSURE_DETAILS_URL = 'https://kind.krx.co.kr/disclosure/details.do'
KIND_DISCLOSURE_VIEWER_URL = 'https://kind.krx.co.kr/common/disclsviewer.do'
KIND_TRADING_HALT_URL = 'https://kind.krx.co.kr/investwarn/tradinghaltissue.do'
NAVER_DAILY_PRICE_URL = 'https://api.finance.naver.com/siseJson.naver'
KIND_INVEST_WARNING_LOOKBACK_YEARS = 3
KIND_TRADING_HALT_MARKET_TYPES = ('1', '2', '6')
STANDARD_RELEASE_RATES = {'fiveDay': 0.6, 'fifteenDay': 1.0}

KIND_HEADERS = {
    **BROWSER_HEADERS,
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kind.krx.co.kr/',
}
KIND_POST_HEADERS = {
    **KIND_HEADERS,
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}
NAVER_HEADERS = {
    **BROWSER_HEADERS,
    'Accept': '*/*',
    'Referer': 'https://finance.naver.com/',
}


class InvestmentWarningStatusError(RuntimeError):
    def __init__(self, message: str, code: str = 'PROVIDER_ERROR'):
        super().__init__(message)
        self.code = code


def get_investment_warning_status(stock_code: str, now: datetime | date | None = None) -> dict:
    normalized_stock_code = (stock_code or '').strip()
    if not re.fullmatch(r'\d{6}', normalized_stock_code):
        raise ValueError('stockCode는 6자리 종목코드여야 합니다.')

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


def fetch_investment_warning_rows(stock_code: str, now: datetime | date | None = None) -> list[dict]:
    end_date = format_kst_date(now)
    start_date = format_kst_date_years_before(now, KIND_INVEST_WARNING_LOOKBACK_YEARS)
    body = {
        'method': 'investattentwarnriskySub',
        'currentPageSize': '3000',
        'pageIndex': '1',
        'orderMode': '3',
        'orderStat': 'D',
        'searchCodeType': 'number',
        'searchCorpName': '',
        'repIsuSrtCd': f'A{stock_code}',
        'menuIndex': '2',
        'forward': 'invstwarnisu_down',
        'searchFromDate': end_date,
        'startDate': start_date,
        'endDate': end_date,
        'marketType': '',
    }
    html = kind_post_text(KIND_INVEST_WARNING_URL, body)
    rows = parse_kind_investment_warning_rows(html)
    if not rows and not is_kind_empty_result(html):
        raise InvestmentWarningStatusError('KIND 투자경고 응답을 해석할 수 없습니다.', 'PARSE')
    return rows


def fetch_current_trading_halt_status(stock_code: str) -> dict:
    first_error: Exception | None = None
    for market_type in KIND_TRADING_HALT_MARKET_TYPES:
        body = {
            'method': 'searchTradingHaltIssueSub',
            'currentPageSize': '3000',
            'pageIndex': '1',
            'searchMode': '',
            'searchCodeType': '',
            'searchCorpName': '',
            'repIsuSrtCd': stock_code,
            'forward': 'tradinghaltissue_sub',
            'paxreq': '',
            'outsvcno': '',
            'marketType': market_type,
        }
        try:
            status = parse_kind_current_trading_halt_status(
                kind_post_text(KIND_TRADING_HALT_URL, body),
            )
        except Exception as exc:
            if first_error is None:
                first_error = exc
            continue
        if status['status'] == 'halted':
            return status

    if first_error is not None:
        return {
            'status': 'unknown',
            'reason': str(first_error) or 'KIND 매매거래정지 상태를 확인할 수 없습니다.',
        }

    return {'status': 'not_halted', 'reason': None}


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


def fetch_investment_warning_designation_disclosure(warning_row: dict) -> dict:
    disclosure = fetch_investment_warning_designation_disclosure_reference(warning_row)
    viewer_url = _url_with_params(KIND_DISCLOSURE_VIEWER_URL, {
        'method': 'search',
        'acptno': disclosure['acptNo'],
        'docno': '',
        'viewerhost': '',
        'viewerport': '',
    })
    viewer_html = kind_get_text(viewer_url)
    doc_no = parse_kind_disclosure_viewer_doc_no(viewer_html)
    if not doc_no:
        raise InvestmentWarningStatusError('KIND 지정 공시 문서번호를 찾을 수 없습니다.', 'PARSE')

    contents_url = _url_with_params(KIND_DISCLOSURE_VIEWER_URL, {
        'method': 'searchContents',
        'docNo': doc_no,
    })
    contents_html = kind_get_text(contents_url)
    disclosure_url = parse_kind_disclosure_document_url(contents_html)
    if not disclosure_url:
        raise InvestmentWarningStatusError('KIND 지정 공시 원문 경로를 찾을 수 없습니다.', 'PARSE')

    return {
        'url': disclosure_url,
        'html': kind_get_text(disclosure_url),
    }


def fetch_investment_warning_designation_disclosure_reference(warning_row: dict) -> dict:
    body = {
        'method': 'searchDetailsSub',
        'currentPageSize': '15',
        'pageIndex': '1',
        'orderMode': '1',
        'orderStat': 'D',
        'forward': 'details_sub',
        'searchCodeType': 'number',
        'repIsuSrtCd': f"A{warning_row['stockCode']}",
        'fromDate': warning_row['disclosureDate'],
        'toDate': warning_row['disclosureDate'],
        'reportNm': '투자경고종목지정',
    }
    html = kind_post_text(KIND_DISCLOSURE_DETAILS_URL, body)
    disclosures = parse_kind_disclosure_search_results(html)
    for disclosure in disclosures:
        if '투자경고종목지정' in normalize_disclosure_title(disclosure['title']):
            return disclosure
    raise InvestmentWarningStatusError('KIND 지정 공시를 상세검색에서 찾을 수 없습니다.', 'PARSE')


def resolve_investment_warning_release_conditions(
    stock_code: str,
    judgment_date: str | None,
    now: datetime | date | None,
    release_criteria: dict,
) -> list[dict]:
    if not judgment_date:
        return create_unavailable_release_conditions()

    basis_dates = resolve_release_basis_dates(judgment_date, release_criteria)
    recent_high_start_date = subtract_krx_trading_days(judgment_date, 14)
    today = format_kst_date(now)
    if today < judgment_date:
        return create_future_judgment_release_conditions(
            basis_dates,
            release_criteria,
            judgment_date,
        )

    try:
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


def fetch_daily_close_prices(stock_code: str, start_date: str, end_date: str) -> list[dict]:
    url = _url_with_params(NAVER_DAILY_PRICE_URL, {
        'symbol': stock_code,
        'requestType': '1',
        'startTime': to_compact_date(start_date),
        'endTime': to_compact_date(end_date),
        'timeframe': 'day',
    })
    text = request_text(
        'naver',
        url,
        headers=NAVER_HEADERS,
        timeout=NAVER_PRICE_TIMEOUT,
        retries=1,
        encoding='utf-8',
        errors='replace',
    )
    return parse_naver_daily_close_prices(text)


def kind_post_text(url: str, body: dict[str, str]) -> str:
    raw = request_bytes(
        'krx',
        url,
        data=urllib.parse.urlencode(body).encode('utf-8'),
        method='POST',
        headers=KIND_POST_HEADERS,
        timeout=KRX_KIND_TIMEOUT,
        retries=1,
    )
    return decode_kind_text(raw)


def kind_get_text(url: str) -> str:
    raw = request_bytes(
        'krx',
        url,
        headers=KIND_HEADERS,
        timeout=KRX_KIND_TIMEOUT,
        retries=1,
    )
    return decode_kind_text(raw)


def decode_kind_text(raw: bytes, content_type: str = '') -> str:
    utf8_text = raw.decode('utf-8', errors='replace')
    charset = extract_charset(content_type) or extract_charset(utf8_text)
    if is_euc_kr_charset(charset) or '\ufffd' in utf8_text:
        return raw.decode('euc-kr', errors='replace')
    return utf8_text


def extract_charset(value: str) -> str | None:
    match = re.search(r'charset\s*=\s*["\']?([a-z0-9_-]+)', value, flags=re.I)
    return match.group(1).lower() if match else None


def is_euc_kr_charset(charset: str | None) -> bool:
    return charset in {'euc-kr', 'euckr', 'cp949'}


def parse_kind_investment_warning_rows(html: str) -> list[dict]:
    rows = []
    for row_html in re.findall(r'<tr\b[^>]*>([\s\S]*?)</tr>', html, flags=re.I):
        if re.search(r'<th\b', row_html, flags=re.I):
            continue
        cells = [clean_html_cell(match) for match in re.findall(r'<td\b[^>]*>([\s\S]*?)</td>', row_html, flags=re.I)]
        if len(cells) < 6 or not re.fullmatch(r'\d{6}', cells[2]):
            continue
        rows.append({
            'companyName': cells[1],
            'stockCode': cells[2],
            'disclosureDate': normalize_kind_date(cells[3]),
            'designationDate': normalize_kind_date(cells[4]),
            'releaseDate': None if cells[5] == '-' else normalize_kind_date(cells[5]),
        })
    return rows


def parse_kind_current_trading_halt_status(html: str) -> dict:
    if is_kind_empty_result(html):
        return {'status': 'not_halted', 'reason': None}

    parsed_body_row = False
    for row_html in re.findall(r'<tr\b[^>]*>([\s\S]*?)</tr>', html, flags=re.I):
        if re.search(r'<th\b', row_html, flags=re.I):
            continue
        cells = [clean_html_cell(match) for match in re.findall(r'<td\b[^>]*>([\s\S]*?)</td>', row_html, flags=re.I)]
        if cells:
            parsed_body_row = True
        if len(cells) == 3:
            return {'status': 'halted', 'reason': cells[2] or None}

    if parsed_body_row:
        raise InvestmentWarningStatusError('KIND 매매거래정지 응답을 해석할 수 없습니다.', 'PARSE')
    return {'status': 'not_halted', 'reason': None}


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


def parse_kind_disclosure_search_results(html: str) -> list[dict]:
    disclosures = []
    pattern = re.compile(
        r"openDisclsViewer\('([^']+)'\s*,\s*'[^']*'\)[^>]*title=([\"'])(.*?)\2[^>]*>([\s\S]*?)</a>",
        flags=re.I,
    )
    for match in pattern.finditer(html):
        acpt_no = match.group(1).strip()
        title = clean_html_cell(match.group(4) or match.group(3))
        if acpt_no.isdigit() and title:
            disclosures.append({'acptNo': acpt_no, 'title': title})
    return disclosures


def parse_kind_disclosure_viewer_doc_no(html: str) -> str | None:
    selected = re.search(r'<option\b[^>]*value=["\'](\d+)\|[YN]["\'][^>]*selected[^>]*>', html, flags=re.I)
    if selected:
        return selected.group(1)
    first = re.search(r'<option\b[^>]*value=["\'](\d+)\|[YN]["\'][^>]*>\s*투자경고종목지정', html, flags=re.I)
    return first.group(1) if first else None


def parse_kind_disclosure_document_url(html: str) -> str | None:
    match = re.search(r"parent\.setPath\(\s*'[^']*'\s*,\s*'([^']+)'", html, flags=re.I)
    raw_url = unescape(match.group(1)) if match else ''
    if not raw_url:
        return None
    return urllib.parse.urljoin(KIND_DISCLOSURE_VIEWER_URL, raw_url)


def parse_naver_daily_close_prices(text: str) -> list[dict]:
    prices = []
    row_pattern = re.compile(r"\[\s*[\"']?(\d{4}(?:[.-]?\d{2}[.-]?\d{2}))[\"']?\s*,([^\]]+)\]")
    for row_match in row_pattern.finditer(text):
        raw_date = row_match.group(1)
        numeric_values = [
            float(value.replace(',', ''))
            for value in re.findall(r'-?[\d,]+(?:\.\d+)?', row_match.group(2))
        ]
        if not numeric_values:
            continue
        close = numeric_values[0] if ('.' in raw_date or '-' in raw_date) else (
            numeric_values[3] if len(numeric_values) > 3 else float('nan')
        )
        if close <= 0:
            continue
        prices.append({'date': normalize_naver_price_date(raw_date), 'close': clean_number(close)})
    return sorted(prices, key=lambda item: item['date'])


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


def create_investment_warning_calculation_basis(trading_halt_status: dict, release_criteria: dict) -> str:
    if trading_halt_status['status'] == 'halted':
        return '현재 매매거래정지 상태라 해제 가능일 산정을 보류합니다.'
    if trading_halt_status['status'] == 'unknown':
        return '매매거래정지 상태를 확인할 수 없어 해제 가능일 산정을 보류합니다.'
    if release_criteria['source'] == 'kind_disclosure':
        return 'KIND 지정 공시 원문 해제요건 기준입니다.'
    return f"KIND 지정 공시 해제요건 파싱 실패로 기본 기준을 사용했습니다. 사유: {release_criteria.get('fallbackReason', '')}"


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


def resolve_next_investment_warning_judgment_date(first_judgment_date: str, now: datetime | date | None = None) -> str:
    today = format_kst_date(now)
    if today <= first_judgment_date:
        return first_judgment_date
    return krx_trading_day_on_or_after(today)


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


def _is_supported_trading_day(day: date) -> bool:
    if day.year > MAX_HOLIDAY_YEAR:
        raise InvestmentWarningStatusError(f'공휴일 데이터가 {MAX_HOLIDAY_YEAR}년까지만 있습니다.', 'CALENDAR_RANGE')
    return is_trading_day(day)


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvestmentWarningStatusError(f'날짜 형식이 올바르지 않습니다: {value}', 'PARSE') from exc


def normalize_kind_date(value: str) -> str:
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return value
    raise InvestmentWarningStatusError(f'KIND 날짜 형식이 올바르지 않습니다: {value}', 'PARSE')


def normalize_naver_price_date(value: str) -> str:
    if re.fullmatch(r'\d{8}', value):
        return f'{value[:4]}-{value[4:6]}-{value[6:8]}'
    return value.replace('.', '-')


def extract_kind_document_text(html: str) -> str:
    text = unescape(
        re.sub(
            r'<[^>]*>',
            ' ',
            re.sub(r'<br\b[^>]*>', '\n', re.sub(r'<!--[\s\S]*?-->', ' ', html), flags=re.I),
        )
    )
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r'\s*\n\s*', '\n', text)
    return re.sub(r'\n+', '\n', text).strip()


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


def normalize_disclosure_title(value: str) -> str:
    return re.sub(r'\s+', '', value)


def clean_html_cell(value: str) -> str:
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]*>', '', value))).strip()


def is_kind_empty_result(html: str) -> bool:
    return '조회된 결과값이 없습니다' in html or re.search(r'colspan=["\']?\d+', html, flags=re.I) is not None


def to_compact_date(value: str) -> str:
    return value.replace('-', '')


def _url_with_params(base_url: str, params: dict[str, str]) -> str:
    return f'{base_url}?{urllib.parse.urlencode(params)}'


def clean_number(value: float | int) -> float | int:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
