"""재무 모델 빌더 — DART 전체계정 데이터를 Model 시트 양식 JSON으로 변환.

설계 노트:
- 본 MVP는 DART Open API(fnlttSinglAcntAll)만 사용 → P&L/BS/CF 메인 계정 약 70% 커버.
- 미지원 필드(인건비, 광고선전비, 토지/설비 등 세부, 직원수, 환율)는 null 반환.
- 추후 어댑터 추가 시 build_model() 내부에서 enrich_*()만 호출 추가.
"""
import json, os
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.dart_full import fetch_all
from lib.period import derive_single_quarters, yoy, safe_div, QUARTER_REPRT

_MAPPING_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'data', 'account-mapping.json')

with open(_MAPPING_PATH, encoding='utf-8') as _f:
    MAPPING = json.load(_f)


def _to_num(s):
    if s is None or s == '' or s == '-':
        return None
    try:
        return float(str(s).replace(',', ''))
    except (ValueError, TypeError):
        return None


def _index_accounts(api_response: dict, fs_div: str) -> dict:
    """DART API 응답 → {account_id: amount} 인덱스. 같은 sj_div(BS/IS/CIS/CF) 내에서.
    분기 보고서의 경우 thstrm_amount는 누적금액(IS/CF), BS는 시점값.
    """
    if api_response.get('status') != '000':
        return {}
    out = {}
    for item in api_response.get('list', []):
        if item.get('fs_div') != fs_div:
            continue
        aid = item.get('account_id', '')
        anm = item.get('account_nm', '')
        amt = _to_num(item.get('thstrm_amount'))
        if amt is None:
            continue
        # account_id 우선, 동일 키는 sj_div로 구분(BS/IS/CIS/CF)
        sj = item.get('sj_div', '')
        out[f'{sj}::{aid}'] = amt
        out[f'{sj}::name::{anm}'] = amt
    return out


def _resolve(idx: dict, sj: str, candidates: dict):
    """candidates: {ids: [...], names: [...]} → 첫 매칭 amount or None."""
    for aid in candidates.get('ids', []):
        v = idx.get(f'{sj}::{aid}')
        if v is not None:
            return v
    for nm in candidates.get('names', []):
        v = idx.get(f'{sj}::name::{nm}')
        if v is not None:
            return v
    return None


def _extract_period(api_response: dict, fs_div: str) -> dict:
    """단일 보고서 응답 → 표준화된 필드 dict."""
    idx = _index_accounts(api_response, fs_div)
    out = {}
    # IS — 손익계산서/포괄손익계산서. sj_div는 IS 또는 CIS
    for key, cand in MAPPING['is'].items():
        out[key] = _resolve(idx, 'IS', cand) or _resolve(idx, 'CIS', cand)
    # BS
    for key, cand in MAPPING['bs'].items():
        out[key] = _resolve(idx, 'BS', cand)
    # CF
    for key, cand in MAPPING['cf'].items():
        out[key] = _resolve(idx, 'CF', cand)
    return out


def _fetch_period_safe(corp_code: str, year: str, reprt: str, fs_div: str):
    try:
        return fetch_all(corp_code, year, reprt, fs_div)
    except Exception as e:
        return {'status': 'ERR', 'message': str(e)}


def _annual_to_quarterly(annual_periods: dict) -> dict:
    """{quarter: period_dict} 누적 → 단일 분기로 변환 (IS/CF만, BS는 시점값 그대로 유지)"""
    flow_keys = list(MAPPING['is'].keys()) + list(MAPPING['cf'].keys())
    stock_keys = list(MAPPING['bs'].keys())
    quarters = ['1Q', '2Q', '3Q', '4Q']

    result = {q: {} for q in quarters}
    # Flow: 누적 → 단일 분기
    for key in flow_keys:
        cumulative = {q: annual_periods.get(q, {}).get(key) for q in quarters}
        derived = derive_single_quarters(cumulative)
        for q in quarters:
            result[q][key] = derived[q]
    # Stock: 시점값 그대로
    for key in stock_keys:
        for q in quarters:
            result[q][key] = annual_periods.get(q, {}).get(key)
    return result


def _enrich_derived(period: dict) -> dict:
    """파생 지표 계산 — YoY 제외(다년 비교 필요)."""
    rev = period.get('revenue')
    period['gpm'] = safe_div(period.get('gross_profit'), rev)
    period['opm'] = safe_div(period.get('operating_income'), rev)
    period['npm'] = safe_div(period.get('net_income'), rev)
    period['tax_rate'] = safe_div(period.get('income_tax'), period.get('pretax_income'))
    # 차입금 = 단기 + 장기
    st = period.get('st_borrowings') or 0
    lt = period.get('lt_borrowings') or 0
    if period.get('st_borrowings') is not None or period.get('lt_borrowings') is not None:
        period['total_borrowings'] = st + lt
    else:
        period['total_borrowings'] = None
    # 순현금 = 현금 - 차입금
    cash = period.get('cash')
    if cash is not None and period['total_borrowings'] is not None:
        period['net_cash'] = cash - period['total_borrowings']
    else:
        period['net_cash'] = None
    # CAPEX = 유형자산 취득 + 무형자산 취득
    capex_p = period.get('capex_ppe') or 0
    capex_i = period.get('capex_intangible') or 0
    if period.get('capex_ppe') is not None or period.get('capex_intangible') is not None:
        period['capex'] = capex_p + capex_i
    else:
        period['capex'] = None
    return period


def build_model(corp_code: str, fs_div: str = 'CFS', years: int = 5) -> dict:
    """
    Args:
        corp_code: DART 8자리 corp_code
        fs_div: 'CFS'(연결) or 'OFS'(별도)
        years: 조회할 연수 (현재년-1 부터 역순)
    Returns:
        {
          'meta': {corp_code, fs_div, years_requested, last_period},
          'annual': { '2020': {...}, '2021': {...}, ... },
          'quarterly': { '1Q23': {...}, '2Q23': {...}, ... }
        }
    """
    from datetime import date
    end_year = date.today().year - 1
    start_year = end_year - years + 1
    year_list = [str(y) for y in range(start_year, end_year + 1)]

    annual = {}
    # 분기 누적 데이터를 연도별로 보관 → 단일 분기로 파생
    quarterly_cumulative = {}  # {year: {quarter: period_dict}}

    # 병렬 페치: 각 연도 × 4 reprt
    tasks = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for y in year_list:
            for reprt in ['11012', '11014', '11013', '11011']:
                tasks.append((y, reprt, ex.submit(_fetch_period_safe, corp_code, y, reprt, fs_div)))

        for y, reprt, fut in tasks:
            resp = fut.result()
            period = _extract_period(resp, fs_div) if resp.get('status') == '000' else {}
            quarter_label = {'11012': '1Q', '11014': '2Q', '11013': '3Q', '11011': '4Q'}[reprt]
            quarterly_cumulative.setdefault(y, {})[quarter_label] = period

            # 사업보고서(11011)는 연간값으로 사용
            if reprt == '11011' and period:
                annual[y] = _enrich_derived(dict(period))

    # 연간 YoY 계산
    sorted_years = sorted(annual.keys())
    for i, y in enumerate(sorted_years):
        if i == 0:
            annual[y]['revenue_yoy'] = None
        else:
            prev_y = sorted_years[i - 1]
            annual[y]['revenue_yoy'] = yoy(annual[y].get('revenue'),
                                           annual[prev_y].get('revenue'))

    # 분기 단일값 + YoY 산출
    quarterly = {}
    for y in year_list:
        single = _annual_to_quarterly(quarterly_cumulative.get(y, {}))
        for q in ['1Q', '2Q', '3Q', '4Q']:
            label = f'{q}{y[2:]}'  # 1Q23
            quarterly[label] = _enrich_derived(dict(single[q]))

    # 분기 YoY (전년 동분기 대비)
    for y in year_list:
        prev_y = str(int(y) - 1)
        for q in ['1Q', '2Q', '3Q', '4Q']:
            cur_label = f'{q}{y[2:]}'
            prev_label = f'{q}{prev_y[2:]}'
            cur = quarterly.get(cur_label, {})
            prev = quarterly.get(prev_label, {})
            cur['revenue_yoy'] = yoy(cur.get('revenue'), prev.get('revenue')) if prev else None

    return {
        'meta': {
            'corp_code': corp_code,
            'fs_div': fs_div,
            'years': year_list,
            'unsupported': MAPPING['_unsupported_mvp']['fields'],
        },
        'annual': annual,
        'quarterly': quarterly,
    }
