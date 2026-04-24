import unittest
from unittest.mock import patch

from lib.errors import DartError
from lib import usecases


class UsecaseTests(unittest.TestCase):
    def test_warning_search_normalizes_query_and_returns_contract(self):
        with patch.object(usecases, 'search_kind', return_value=[{'stockName': '삼성전자'}]) as search:
            payload = usecases.warning_search_payload(' 삼성전자 ')

        search.assert_called_once_with('삼성전자')
        self.assertEqual(payload, {
            'results': [{'stockName': '삼성전자'}],
            'query': '삼성전자',
        })

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


if __name__ == '__main__':
    unittest.main()
