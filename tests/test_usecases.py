import unittest
from datetime import date, datetime
from unittest.mock import patch

from lib.http_client import ExternalAPIError
from lib.errors import DartError
from lib import usecases


class UsecaseTests(unittest.TestCase):
    def test_warning_search_normalizes_query_and_returns_contract(self):
        with (
            patch.object(usecases, 'search_kind', return_value=[{
                'level': '투자경고',
                'stockName': '삼성전자',
                'designationDate': '2026-05-04',
            }]) as search,
            patch.object(usecases, 'resolve_exact_stock_codes', return_value=[{
                'code': '005930',
                'name': '삼성전자',
            }]) as resolve,
            patch.object(usecases, 'get_investment_warning_status') as get_status,
        ):
            payload = usecases.warning_search_payload(' 삼성전자 ')

        search.assert_called_once_with('삼성전자', raise_on_error=True)
        resolve.assert_called_once_with('삼성전자')
        get_status.assert_not_called()
        self.assertEqual(payload, {
            'results': [{
                'level': '투자경고',
                'stockName': '삼성전자',
                'designationDate': '2026-05-04',
                'stockCode': '005930',
            }],
            'query': '삼성전자',
        })

    def test_warning_search_uses_kind_list_stock_code_without_detail_status(self):
        with (
            patch.object(usecases, 'search_kind', return_value=[{
                'level': '투자경고',
                'stockName': '라이콤',
                'designationDate': '2026-05-04',
                'stockCode': '388790',
            }]) as search,
            patch.object(usecases, 'resolve_exact_stock_codes') as resolve,
            patch.object(usecases, 'get_investment_warning_status') as get_status,
        ):
            payload = usecases.warning_search_payload('라이콤')

        search.assert_called_once_with('라이콤', raise_on_error=True)
        resolve.assert_not_called()
        get_status.assert_not_called()
        self.assertEqual(payload, {
            'results': [{
                'level': '투자경고',
                'stockName': '라이콤',
                'designationDate': '2026-05-04',
                'stockCode': '388790',
            }],
            'query': '라이콤',
        })

    def test_warning_search_stays_empty_when_kind_list_is_empty(self):
        with (
            patch.object(usecases, 'search_kind', return_value=[]) as search,
            patch.object(usecases, 'resolve_exact_stock_codes') as resolve,
            patch.object(usecases, 'get_investment_warning_status') as get_status,
        ):
            payload = usecases.warning_search_payload('삼성전자')

        search.assert_called_once_with('삼성전자', raise_on_error=True)
        resolve.assert_not_called()
        get_status.assert_not_called()
        self.assertEqual(payload, {'results': [], 'query': '삼성전자'})

    def test_warning_search_does_not_add_partial_fallback_results(self):
        with (
            patch.object(usecases, 'search_kind', return_value=[]) as search,
            patch.object(usecases, 'get_investment_warning_status') as get_status,
        ):
            payload = usecases.warning_search_payload('라이')

        search.assert_called_once_with('라이', raise_on_error=True)
        get_status.assert_not_called()
        self.assertEqual(payload, {'results': [], 'query': '라이'})

    def test_warning_search_surfaces_non_krx_list_failure(self):
        with (
            patch.object(usecases, 'search_kind', side_effect=RuntimeError('krx down')),
            patch.object(usecases, 'get_investment_warning_status') as get_status,
        ):
            with self.assertRaises(RuntimeError):
                usecases.warning_search_payload('라이콤')

        get_status.assert_not_called()

    def test_warning_search_returns_temporary_limit_message_when_kind_list_is_blocked(self):
        error = ExternalAPIError(
            'krx HTTP 403 while requesting https://kind.krx.co.kr/investwarn/investattentwarnrisky.do',
            provider='krx',
            status=403,
            url='https://kind.krx.co.kr/investwarn/investattentwarnrisky.do',
        )
        with (
            patch.object(usecases, 'search_kind', side_effect=error),
            patch.object(usecases, 'get_investment_warning_status') as get_status,
        ):
            payload = usecases.warning_search_payload('라이콤')

        get_status.assert_not_called()
        self.assertEqual(payload, {
            'results': [],
            'query': '라이콤',
            'message': usecases.KRX_TEMPORARY_LIMIT_MESSAGE,
        })

    def test_stock_code_payload_uses_exact_dart_resolver(self):
        with patch.object(usecases, 'resolve_exact_stock_codes', return_value=[{
            'code': '388790',
            'name': '라이콤',
            'corpCode': '01569102',
        }]) as resolve:
            payload = usecases.stock_code_payload(' 라이콤 ')

        resolve.assert_called_once_with('라이콤')
        self.assertEqual(payload, {
            'items': [{
                'code': '388790',
                'name': '라이콤',
                'corpCode': '01569102',
            }],
            'query': '라이콤',
        })

    def test_stock_code_payload_returns_exact_name_message_on_miss(self):
        with patch.object(usecases, 'resolve_exact_stock_codes', return_value=[]):
            payload = usecases.stock_code_payload('라이')

        self.assertEqual(payload, {
            'items': [],
            'query': '라이',
            'message': usecases.EXACT_STOCK_NAME_MESSAGE,
        })

    def test_investment_warning_status_payload_validates_stock_code(self):
        with self.assertRaises(ValueError):
            usecases.investment_warning_status_payload('00593')

    def test_investment_warning_status_payload_delegates(self):
        with patch.object(
            usecases,
            'get_investment_warning_status',
            return_value={'status': 'not_warning', 'stockCode': '005930'},
        ) as get_status:
            payload = usecases.investment_warning_status_payload('005930')

        get_status.assert_called_once_with('005930')
        self.assertEqual(payload, {'status': 'not_warning', 'stockCode': '005930'})

    def test_stock_price_returns_latest_sixteen_prices(self):
        prices = [
            {'date': f'2026-01-{day:02d}', 'close': 100 + day}
            for day in range(1, 21)
        ]
        with patch.object(usecases, 'fetch_prices', return_value=prices) as fetch:
            payload = usecases.stock_price_payload('005930')

        fetch.assert_called_once_with('005930', count=20)
        self.assertEqual(payload['prices'], prices[-16:])
        self.assertNotIn('warnings', payload)
        self.assertTrue(payload['thresholds'])

    def test_stock_price_surfaces_insufficient_data_warning(self):
        prices = [{'date': '2026-01-01', 'close': 100}]
        with patch.object(usecases, 'fetch_prices', return_value=prices):
            payload = usecases.stock_price_payload('005930')

        self.assertEqual(payload['prices'], prices[-16:])
        self.assertEqual(payload['warnings'][0]['code'], 'INSUFFICIENT_PRICE_DATA')

    def test_dart_search_validates_and_passes_typed_params(self):
        with patch.object(usecases, 'search_disclosure', return_value={'status': '013'}) as search:
            payload = usecases.dart_search_payload(
                corp_code='00126380',
                bgn_de='20250101',
                end_de='20250131',
                page_no='2',
                page_count='10',
                pblntf_ty='A',
            )

        self.assertEqual(payload, {'status': '013'})
        search.assert_called_once_with(
            corp_code='00126380',
            bgn_de='20250101',
            end_de='20250131',
            page_no=2,
            page_count=10,
            pblntf_ty='A',
        )

    def test_dart_search_raises_typed_error_for_provider_status(self):
        with patch.object(
            usecases,
            'search_disclosure',
            return_value={'status': '999', 'message': 'bad request'},
        ):
            with self.assertRaises(DartError) as raised:
                usecases.dart_search_payload(corp_code='00126380')

        self.assertEqual(raised.exception.code, 'DART_API_ERROR')
        self.assertEqual(raised.exception.details['dartStatus'], '999')


class CautionSearchPayloadTests(unittest.TestCase):
    def test_blank_query_returns_not_caution_without_calling_krx(self):
        with patch.object(usecases, 'search_kind_caution') as krx:
            payload = usecases.caution_search_payload('   ')
        self.assertEqual(payload['status'], 'not_caution')
        self.assertEqual(payload['query'], '')
        self.assertIn('todayKst', payload)
        krx.assert_not_called()

    def test_no_krx_results_returns_not_caution(self):
        with patch.object(usecases, 'search_kind_caution', return_value=[]):
            payload = usecases.caution_search_payload('알 수 없는 종목')
        self.assertEqual(payload['status'], 'not_caution')
        self.assertEqual(payload['query'], '알 수 없는 종목')

    def test_today_designation_without_active_notice_is_non_price_reason(self):
        today = datetime.now(usecases.KST).date().isoformat()
        warn = {
            'stockName': '테스트',
            'latestDesignationDate': today,
            'latestDesignationReason': '소수계좌 매수관여 과다',
            'recent15dCount': 1,
            'allDates': [today],
            'entries': [{'date': today, 'reason': '소수계좌 매수관여 과다'}],
            'market': 'KOSPI',
        }
        with patch.object(usecases, 'search_kind_caution', return_value=[warn]):
            payload = usecases.caution_search_payload('테스트')
        self.assertEqual(payload['status'], 'non_price_reason')
        self.assertEqual(payload['stockName'], '테스트')

    def test_active_notice_without_stock_code_returns_code_not_found(self):
        today = date.today()
        notice = today.isoformat()
        warn = {
            'stockName': '코드없음',
            'latestDesignationDate': notice,
            'latestDesignationReason': '투자경고 지정예고',
            'recent15dCount': 1,
            'allDates': [notice],
            'entries': [{'date': notice, 'reason': '투자경고 지정예고'}],
            'market': 'KOSPI',
        }
        with (
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'resolve_exact_stock_codes', return_value=[]),
        ):
            payload = usecases.caution_search_payload('코드없음')
        self.assertEqual(payload['status'], 'code_not_found')
        self.assertIn('activeNotice', payload)

    def test_full_pipeline_returns_ok_with_escalation(self):
        today = date.today()
        notice = today.isoformat()
        warn = {
            'stockName': '풀파이프',
            'latestDesignationDate': notice,
            'latestDesignationReason': '투자경고 지정예고',
            'recent15dCount': 1,
            'allDates': [notice],
            'entries': [{'date': notice, 'reason': '투자경고 지정예고'}],
            'market': 'KOSPI',
        }
        escalation = {
            'tClose': 100,
            'sets': [{'allMet': False}, {'allMet': False}],
            'headline': {'verdict': 'none'},
        }
        with (
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(
                usecases,
                'resolve_exact_stock_codes',
                return_value=[{'code': '005930', 'name': '풀파이프', 'market': 'KOSPI'}],
            ),
            patch.object(usecases, 'fetch_prices', return_value=[]),
            patch.object(usecases, 'fetch_index_prices', return_value=[]),
            patch.object(usecases, 'calc_official_escalation', return_value=escalation),
        ):
            payload = usecases.caution_search_payload('풀파이프')
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['code'], '005930')
        self.assertEqual(payload['indexSymbol'], 'KOSPI')
        self.assertEqual(payload['escalation'], escalation)

    def test_market_to_index_symbol_handles_known_markets(self):
        self.assertEqual(usecases._market_to_index_symbol('KOSDAQ'), 'KOSDAQ')
        self.assertEqual(usecases._market_to_index_symbol('코스닥'), 'KOSDAQ')
        self.assertEqual(usecases._market_to_index_symbol('KOSPI'), 'KOSPI')
        self.assertEqual(usecases._market_to_index_symbol('유가증권시장'), 'KOSPI')
        self.assertEqual(usecases._market_to_index_symbol(''), '')
        self.assertEqual(usecases._market_to_index_symbol('UNKNOWN'), '')

    def test_active_warning_notice_uses_notice_date_as_judgment_day_one(self):
        notice = usecases._active_warning_notice(
            [{'date': '2026-04-24', 'reason': '투자경고 지정예고'}],
            date(2026, 4, 24),
        )

        self.assertEqual(notice['firstJudgmentDate'], '2026-04-24')
        self.assertEqual(notice['lastJudgmentDate'], '2026-05-11')
        self.assertEqual(notice['judgmentDayIndex'], 1)
        self.assertEqual(notice['judgmentWindowRule'], '지정예고일 포함 10거래일')


class MarketAlertForecastPayloadTests(unittest.TestCase):
    def _warn(self, name: str, notice: str, reason: str = '투자경고 지정예고'):
        return {
            'stockName': name,
            'latestDesignationDate': notice,
            'latestDesignationReason': reason,
            'recent15dCount': 1,
            'allDates': [notice],
            'entries': [{'date': notice, 'reason': reason}],
            'market': 'KOSPI',
        }

    def test_forecast_public_payload_returns_cache_miss_without_upstream_calls(self):
        today = date(2026, 4, 24)
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'durable_get_json', return_value=None),
            patch.object(usecases, 'search_kind_caution') as search_kind_caution,
            patch.object(usecases, 'search_kind') as search_kind,
            patch.object(usecases, 'fetch_prices') as fetch_prices,
            patch.object(usecases, 'fetch_index_prices') as fetch_index_prices,
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['cacheInfo']['status'], 'miss')
        self.assertEqual(payload['cacheInfo']['key'], usecases.FORECAST_CACHE_KEY)
        self.assertEqual(payload['summary']['total'], 0)
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['errors'][0]['source'], 'forecast-cache')
        search_kind_caution.assert_not_called()
        search_kind.assert_not_called()
        fetch_prices.assert_not_called()
        fetch_index_prices.assert_not_called()

    def test_forecast_public_payload_returns_cached_snapshot_with_cache_info(self):
        cached = {
            'todayKst': '2026-04-26',
            'generatedAt': '2026-04-26T09:10:00+09:00',
            'policy': {'name': 'policy'},
            'summary': {'total': 1},
            'items': [{'stockName': '캐시종목'}],
            'errors': [],
        }
        with (
            patch.object(usecases, 'durable_get_json', return_value=cached),
            patch.object(usecases, 'search_kind_caution') as search_kind_caution,
        ):
            payload = usecases.market_alert_forecast_payload()

        self.assertEqual(payload['cacheInfo']['status'], 'hit')
        self.assertEqual(payload['cacheInfo']['key'], usecases.FORECAST_CACHE_KEY)
        self.assertIsInstance(payload['cacheInfo']['ageSeconds'], int)
        self.assertEqual(payload['summary']['total'], 1)
        self.assertEqual(payload['items'][0]['stockName'], '캐시종목')
        search_kind_caution.assert_not_called()

    def test_refresh_forecast_cache_builds_and_stores_snapshot(self):
        snapshot = {
            'todayKst': '2026-04-26',
            'generatedAt': '2026-04-26T16:10:00+09:00',
            'summary': {'total': 2},
            'items': [],
            'errors': [],
        }
        with (
            patch.object(usecases, 'build_market_alert_forecast_payload', return_value=snapshot),
            patch.object(usecases, 'durable_set_json') as durable_set_json,
        ):
            result = usecases.refresh_market_alert_forecast_cache()

        durable_set_json.assert_called_once_with(
            usecases.FORECAST_CACHE_KEY,
            snapshot,
            ttl=usecases.FORECAST_CACHE_TTL_SECONDS,
        )
        self.assertEqual(result['key'], usecases.FORECAST_CACHE_KEY)
        self.assertEqual(result['ttlSeconds'], usecases.FORECAST_CACHE_TTL_SECONDS)
        self.assertEqual(result['summary'], {'total': 2})

    def test_forecast_filters_active_notices_and_excludes_current_warning(self):
        today = date(2026, 4, 24)
        notice = '2026-04-23'

        def codes(name):
            return [{'code': '000001' if name == '경보종목' else '000002', 'name': name, 'market': 'KOSPI'}]

        def prices(code, count=30):
            close = 1 if code == '000001' else 2
            return [{'date': '2026-04-24', 'close': close} for _ in range(16)]

        def escalation(stock_prices, index_prices):
            if stock_prices[-1]['close'] == 1:
                return {
                    'headline': {'verdict': 'strong', 'matchedSet': 0},
                    'sets': [{'label': '단기급등', 'allMet': True}],
                }
            return {
                'headline': {'verdict': 'none', 'matchedSet': None},
                'sets': [{'label': '단기급등', 'allMet': False}],
            }

        rows = [
            self._warn('경보종목', notice),
            self._warn('주의종목', notice),
            self._warn('현재경고', notice),
        ]
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[{
                'stockName': '현재경고',
                'level': '투자경고',
                'designationDate': notice,
            }]),
            patch.object(usecases, 'search_kind_caution', return_value=rows),
            patch.object(usecases, 'resolve_exact_stock_codes', side_effect=codes),
            patch.object(usecases, 'fetch_prices', side_effect=prices),
            patch.object(usecases, 'fetch_index_prices', return_value=[{'date': '2026-04-24', 'close': 1.0} for _ in range(16)]),
            patch.object(usecases, 'calc_official_escalation', side_effect=escalation),
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 2)
        self.assertEqual(payload['summary']['alert'], 1)
        self.assertEqual(payload['summary']['watch'], 1)
        self.assertEqual(payload['summary']['excludedCurrentWarning'], 1)
        self.assertEqual(payload['items'][0]['stockName'], '경보종목')
        self.assertEqual(payload['items'][0]['levelLabel'], '경보')

    def test_forecast_keeps_released_warning_history_as_candidate(self):
        today = date(2026, 4, 24)
        warn = self._warn('재예고종목', '2026-04-23')
        released_prices = [
            {'date': f'2026-04-{day:02d}', 'close': 100}
            for day in range(1, 21)
        ]

        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[{
                'stockName': '재예고종목',
                'level': '투자경고',
                'designationDate': '2026-03-02',
            }]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'resolve_exact_stock_codes', return_value=[{
                'code': '000004',
                'name': '재예고종목',
                'market': 'KOSPI',
            }]),
            patch.object(usecases, 'fetch_prices', return_value=released_prices),
            patch.object(usecases, 'fetch_index_prices', return_value=[
                {'date': '2026-04-20', 'close': 1.0}
                for _ in range(16)
            ]),
            patch.object(usecases, 'calc_official_escalation', return_value={
                'headline': {'verdict': 'none', 'matchedSet': None},
                'sets': [{'label': '단기급등', 'allMet': False}],
            }),
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['excludedCurrentWarning'], 0)
        self.assertEqual(payload['summary']['total'], 1)
        self.assertEqual(payload['items'][0]['stockName'], '재예고종목')

    def test_forecast_does_not_treat_investment_risk_rows_as_current_warning(self):
        current_names, errors = usecases._current_warning_candidate_names(
            [{
                'stockName': '위험행',
                'level': '투자위험',
                'designationDate': '2026-04-23',
            }],
            {'위험행'},
            date(2026, 4, 24),
        )

        self.assertEqual(current_names, set())
        self.assertEqual(errors, [])

    def test_forecast_caution_fetch_failure_surfaces_error(self):
        today = date(2026, 4, 24)
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind_caution', side_effect=RuntimeError('krx down')),
            patch.object(usecases, 'search_kind') as search_kind,
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 0)
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['errors'][0]['source'], 'krx-caution')
        self.assertIn('krx down', payload['errors'][0]['message'])
        search_kind.assert_not_called()

    def test_forecast_caution_krx_403_uses_user_safe_message(self):
        today = date(2026, 4, 24)
        error = usecases.ExternalAPIError(
            'krx HTTP 403 while requesting https://kind.krx.co.kr/blocked',
            provider='krx',
            status=403,
            url='https://kind.krx.co.kr/blocked',
        )
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind_caution', side_effect=error),
            patch.object(usecases, 'search_kind') as search_kind,
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 0)
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['errors'][0]['source'], 'krx-caution')
        self.assertIn('배포 서버 조회를 일시적으로 제한', payload['errors'][0]['message'])
        self.assertNotIn('https://kind.krx.co.kr', payload['errors'][0]['message'])
        search_kind.assert_not_called()

    def test_forecast_warning_fetch_failure_surfaces_error(self):
        today = date(2026, 4, 24)
        warn = self._warn('조회오류후보', '2026-04-23')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'search_kind', side_effect=RuntimeError('warning down')),
            patch.object(usecases, 'resolve_exact_stock_codes', return_value=[{
                'code': '000005',
                'name': '조회오류후보',
                'market': 'KOSPI',
            }]),
            patch.object(usecases, 'fetch_prices', return_value=[
                {'date': f'2026-04-{day:02d}', 'close': 100}
                for day in range(1, 21)
            ]),
            patch.object(usecases, 'fetch_index_prices', return_value=[
                {'date': '2026-04-20', 'close': 1.0}
                for _ in range(16)
            ]),
            patch.object(usecases, 'calc_official_escalation', return_value={
                'headline': {'verdict': 'none', 'matchedSet': None},
                'sets': [{'label': '단기급등', 'allMet': False}],
            }),
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 1)
        self.assertEqual(payload['errors'][0]['source'], 'krx-warning')
        self.assertIn('warning down', payload['errors'][0]['message'])

    def test_forecast_marks_internal_review_reason_without_price_calls(self):
        today = date(2026, 4, 24)
        warn = self._warn('불건전종목', '2026-04-23', '투자경고 지정예고 · 단기상승·불건전요건')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'resolve_exact_stock_codes') as resolve_exact_stock_codes,
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['needsReview'], 1)
        self.assertEqual(payload['items'][0]['calcStatus'], 'needs_review')
        resolve_exact_stock_codes.assert_not_called()

    def test_forecast_price_failure_is_review_needs_review(self):
        today = date(2026, 4, 24)
        warn = self._warn('가격오류', '2026-04-23')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
            patch.object(usecases, 'resolve_exact_stock_codes', return_value=[{'code': '000003', 'name': '가격오류', 'market': 'KOSPI'}]),
            patch.object(usecases, 'fetch_prices', side_effect=RuntimeError('timeout')),
            patch.object(usecases, 'fetch_index_prices', return_value=[{'date': '2026-04-24', 'close': 1.0} for _ in range(16)]),
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['needsReview'], 1)
        self.assertEqual(payload['items'][0]['level'], 'review')
        self.assertEqual(payload['items'][0]['calcStatus'], 'needs_review')
        self.assertIn('timeout', payload['items'][0]['calcDetail'])

    def test_forecast_ignores_expired_notice(self):
        today = date(2026, 4, 24)
        warn = self._warn('만료종목', '2026-03-01')
        with (
            patch.object(usecases, '_today_kst_date', return_value=today),
            patch.object(usecases, 'search_kind', return_value=[]),
            patch.object(usecases, 'search_kind_caution', return_value=[warn]),
        ):
            payload = usecases.build_market_alert_forecast_payload()

        self.assertEqual(payload['summary']['total'], 0)


if __name__ == '__main__':
    unittest.main()
