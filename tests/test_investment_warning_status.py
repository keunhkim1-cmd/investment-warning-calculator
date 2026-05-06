from __future__ import annotations

from datetime import datetime

import pytest

from lib import investment_warning_status as iws


def investment_warning_download_html(
    *,
    stock_code='047040',
    company_name='Daewoo E&amp;C',
    disclosure_date='2026-04-13',
    designation_date='2026-04-14',
    release_date='-',
):
    return f'''
      <table>
        <tr>
          <th>번호</th><th>종목명</th><th>종목코드</th><th>공시일</th><th>지정일</th><th>해제일</th>
        </tr>
        <tr>
          <td>1</td><td>{company_name}</td><td>{stock_code}</td>
          <td>{disclosure_date}</td><td>{designation_date}</td><td>{release_date}</td>
        </tr>
      </table>
    '''


def no_investment_warning_download_html():
    return '<td class="first null" colspan="5">조회된 결과값이 없습니다.</td>'


def current_trading_halt_html(reason='조회공시 요구'):
    return f'''
      <table><tbody><tr><td>1</td><td>Daewoo E&amp;C</td><td>{reason}</td></tr></tbody></table>
    '''


def no_current_trading_halt_html():
    return '<td class="first null" colspan="3">조회된 결과값이 없습니다.</td>'


def investment_warning_disclosure_html(
    *,
    company_name='티엘비',
    designation_date_text='2026년 04월 17일',
    five_day_rate=45,
    fifteen_day_rate=75,
    first_judgment_text='04월 30일',
    t_minus_five_text='04월 23일',
    t_minus_fifteen_text='04월 09일',
):
    return f'''
      <span>
        투자경고종목 지정<br>
        | 1. 대상종목 | {company_name} | 보통주 |<br>
        | 2. 지정일 | {designation_date_text} |<br>
        | 5. 해제요건 | 위 종목은 지정일부터 계산하여 10일째 되는 날 이후의 날로서 |<br>
        | | 어느 특정일(판단일, T)에 다음 사항에 모두 해당하지 않을 경우 |<br>
        | | 그 다음 날에 해제됨 |<br>
        | | ① 판단일(T)의 종가가 5일 전날(T-5)의 종가보다 {five_day_rate}% 이상 상승 |<br>
        | | ② 판단일(T)의 종가가 15일 전날(T-15)의 종가보다 {fifteen_day_rate}% 이상 상승 |<br>
        | | ③ 판단일(T)의 종가가 최근 15일 종가중 최고가 |<br>
        | | *투자경고종목 해제여부의 최초 판단일은 {first_judgment_text}(예정) 이며, |<br>
        | | 5일 전날 및 15일 전날은 각각 {t_minus_five_text} 및 {t_minus_fifteen_text}(예정)이며, |<br>
        | | 그 날 해제요건에 해당되지 않을 경우 하루씩 순연하여 판단함 |<br>
      </span>
    '''


def daily_prices(latest_close=46_000):
    rows = [
        ('2026-04-10', 25_000),
        ('2026-04-13', 28_000),
        ('2026-04-14', 29_000),
        ('2026-04-15', 31_000),
        ('2026-04-16', 34_000),
        ('2026-04-17', 37_000),
        ('2026-04-20', 40_000),
        ('2026-04-21', 42_000),
        ('2026-04-22', 44_000),
        ('2026-04-23', 45_000),
        ('2026-04-24', 30_000),
        ('2026-04-27', 43_000),
        ('2026-04-28', 45_500),
        ('2026-04-29', 47_000),
        ('2026-04-30', latest_close),
    ]
    return [{'date': day, 'close': close} for day, close in rows]


def test_parses_kind_investment_warning_rows():
    rows = iws.parse_kind_investment_warning_rows(
        investment_warning_download_html(company_name='THE E&amp;M', stock_code='089230')
    )

    assert rows == [{
        'companyName': 'THE E&M',
        'stockCode': '089230',
        'disclosureDate': '2026-04-13',
        'designationDate': '2026-04-14',
        'releaseDate': None,
    }]


def test_parses_current_kind_trading_halt_rows():
    assert iws.parse_kind_current_trading_halt_status(
        current_trading_halt_html(reason='풍문 또는 보도 관련')
    ) == {'status': 'halted', 'reason': '풍문 또는 보도 관련'}
    assert iws.parse_kind_current_trading_halt_status(no_current_trading_halt_html()) == {
        'status': 'not_halted',
        'reason': None,
    }


def test_parses_naver_daily_close_rows():
    text = '''
      [
        ['날짜', '시가', '고가', '저가', '종가', '거래량'],
        ["20260430", 85000, 88100, 83900, 87500, 272688],
        ["2026.05.04", 88000, 0, 0, 0, 1000]
      ]
    '''
    assert iws.parse_naver_daily_close_prices(text) == [
        {'date': '2026-04-30', 'close': 87500},
        {'date': '2026-05-04', 'close': 88000},
    ]


def test_parses_release_criteria_from_kind_disclosure_euc_kr():
    html = iws.decode_kind_text(investment_warning_disclosure_html().encode('euc-kr'))
    assert iws.parse_kind_investment_warning_release_criteria(
        html,
        designation_date='2026-04-17',
        disclosure_url='https://kind.krx.co.kr/external/2026/04/16/doc.htm',
    ) == {
        'source': 'kind_disclosure',
        'fiveDayThresholdRate': 0.45,
        'fifteenDayThresholdRate': 0.75,
        'firstJudgmentDate': '2026-04-30',
        'tMinusFiveDate': '2026-04-23',
        'tMinusFifteenDate': '2026-04-09',
        'disclosureUrl': 'https://kind.krx.co.kr/external/2026/04/16/doc.htm',
        'fallbackReason': None,
    }


def install_status_stubs(monkeypatch, *, prices=None, halt_status=None, rows=None):
    warning_row = {
        'companyName': 'Daewoo E&C',
        'stockCode': '047040',
        'disclosureDate': '2026-04-13',
        'designationDate': '2026-04-14',
        'releaseDate': None,
    }
    monkeypatch.setattr(iws, 'fetch_investment_warning_rows', lambda stock_code, now=None: rows if rows is not None else [warning_row])
    monkeypatch.setattr(iws, 'fetch_current_trading_halt_status', lambda stock_code: halt_status or {'status': 'not_halted', 'reason': None})
    monkeypatch.setattr(iws, 'fetch_investment_warning_designation_disclosure', lambda row: (_ for _ in ()).throw(RuntimeError('disclosure unavailable')))
    monkeypatch.setattr(iws, 'fetch_daily_close_prices', lambda stock_code, start, end: prices or daily_prices())


def test_returns_investment_warning_forecast_from_current_rows(monkeypatch):
    install_status_stubs(monkeypatch)

    status = iws.get_investment_warning_status(
        '047040',
        datetime.fromisoformat('2026-05-03T00:00:00+09:00'),
    )

    assert status['status'] == 'investment_warning'
    assert status['firstJudgmentDate'] == '2026-04-27'
    assert status['nextJudgmentDate'] == '2026-05-04'
    assert status['expectedReleaseDate'] == '2026-05-06'
    assert status['releaseCriteria']['source'] == 'fallback'
    assert status['releaseConditions'] == [
        {
            'type': 'five_day_gain',
            'status': 'safe',
            'basisDate': '2026-04-24',
            'basisPrice': 30000,
            'thresholdRate': 0.6,
            'thresholdPrice': 48000,
            'evaluationDate': '2026-04-30',
            'evaluationPrice': 46000,
        },
        {
            'type': 'fifteen_day_gain',
            'status': 'safe',
            'basisDate': '2026-04-10',
            'basisPrice': 25000,
            'thresholdRate': 1.0,
            'thresholdPrice': 50000,
            'evaluationDate': '2026-04-30',
            'evaluationPrice': 46000,
        },
        {
            'type': 'fifteen_day_high',
            'status': 'safe',
            'basisDate': '2026-04-29',
            'basisPrice': 47000,
            'thresholdRate': None,
            'thresholdPrice': 47000,
            'evaluationDate': '2026-04-30',
            'evaluationPrice': 46000,
        },
    ]


def test_uses_disclosure_criteria_instead_of_standard_rates(monkeypatch):
    install_status_stubs(monkeypatch, prices=[
        {'date': '2026-04-09', 'close': 1000},
        {'date': '2026-04-10', 'close': 1050},
        {'date': '2026-04-13', 'close': 1100},
        {'date': '2026-04-14', 'close': 1150},
        {'date': '2026-04-15', 'close': 1200},
        {'date': '2026-04-16', 'close': 1250},
        {'date': '2026-04-17', 'close': 1300},
        {'date': '2026-04-20', 'close': 1350},
        {'date': '2026-04-21', 'close': 1400},
        {'date': '2026-04-22', 'close': 1420},
        {'date': '2026-04-23', 'close': 1000},
        {'date': '2026-04-24', 'close': 1430},
        {'date': '2026-04-27', 'close': 1440},
        {'date': '2026-04-28', 'close': 1460},
        {'date': '2026-04-29', 'close': 1470},
        {'date': '2026-04-30', 'close': 1400},
    ], rows=[{
        'companyName': 'TLB',
        'stockCode': '356860',
        'disclosureDate': '2026-04-16',
        'designationDate': '2026-04-17',
        'releaseDate': None,
    }])
    monkeypatch.setattr(iws, 'fetch_investment_warning_designation_disclosure', lambda row: {
        'url': 'https://kind.krx.co.kr/external/2026/04/16/doc.htm',
        'html': investment_warning_disclosure_html(),
    })

    status = iws.get_investment_warning_status(
        '356860',
        datetime.fromisoformat('2026-04-30T00:00:00+09:00'),
    )

    assert status['releaseCriteria']['source'] == 'kind_disclosure'
    assert status['releaseCriteria']['fiveDayThresholdRate'] == 0.45
    assert status['releaseCriteria']['fifteenDayThresholdRate'] == 0.75
    assert status['releaseConditions'][0]['thresholdPrice'] == 1450
    assert status['releaseConditions'][1]['thresholdPrice'] == 1750


def test_marks_release_conditions_as_exceeded(monkeypatch):
    install_status_stubs(monkeypatch, prices=daily_prices(latest_close=51_000))

    status = iws.get_investment_warning_status(
        '047040',
        datetime.fromisoformat('2026-05-03T00:00:00+09:00'),
    )

    assert [condition['status'] for condition in status['releaseConditions']] == [
        'exceeded',
        'exceeded',
        'exceeded',
    ]


def test_holds_release_forecast_when_currently_halted(monkeypatch):
    install_status_stubs(monkeypatch, halt_status={'status': 'halted', 'reason': 'halted'})

    status = iws.get_investment_warning_status(
        '047040',
        datetime.fromisoformat('2026-05-03T00:00:00+09:00'),
    )

    assert status['nextJudgmentDate'] is None
    assert status['expectedReleaseDate'] is None
    assert status['tradingHaltReason'] == 'halted'
    assert {condition['status'] for condition in status['releaseConditions']} == {'unavailable'}


def test_holds_release_forecast_when_halt_status_unknown(monkeypatch):
    install_status_stubs(monkeypatch, halt_status={'status': 'unknown', 'reason': 'temporary KIND outage'})

    status = iws.get_investment_warning_status(
        '047040',
        datetime.fromisoformat('2026-05-03T00:00:00+09:00'),
    )

    assert status['calculationBasis'] == '매매거래정지 상태를 확인할 수 없어 해제 가능일 산정을 보류합니다.'
    assert status['tradingHaltReason'] == 'temporary KIND outage'
    assert {condition['status'] for condition in status['releaseConditions']} == {'unavailable'}


def test_returns_not_warning_when_stock_absent(monkeypatch):
    install_status_stubs(monkeypatch, rows=[])

    assert iws.get_investment_warning_status('005930')['status'] == 'not_warning'


def test_validates_stock_code():
    with pytest.raises(ValueError, match='stockCode'):
        iws.get_investment_warning_status('00593')
