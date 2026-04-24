import unittest
from unittest.mock import patch

from lib import financial_model


class FinancialModelResultCacheTests(unittest.TestCase):
    def setUp(self):
        financial_model._result_cache.clear()

    def tearDown(self):
        financial_model._result_cache.clear()

    def test_build_model_reuses_non_empty_result_cache(self):
        response = {
            'status': '000',
            'list': [{
                'sj_div': 'IS',
                'account_id': 'ifrs-full_Revenue',
                'account_nm': '매출액',
                'thstrm_amount': '100',
            }],
        }

        with (
            patch.object(financial_model, '_load_cache', return_value={}) as load_cache,
            patch.object(financial_model, '_save_cache') as save_cache,
            patch.object(financial_model, '_fetch_period_safe', return_value=response) as fetch_period,
        ):
            first = financial_model.build_model('00126380', fs_div='CFS', years=1)
            second = financial_model.build_model('00126380', fs_div='CFS', years=1)

        self.assertEqual(first, second)
        self.assertEqual(fetch_period.call_count, 4)
        self.assertEqual(load_cache.call_count, 1)
        self.assertEqual(save_cache.call_count, 1)

    def test_build_model_does_not_cache_fully_empty_result(self):
        response = {'status': '013', 'list': []}

        with (
            patch.object(financial_model, '_load_cache', return_value={}),
            patch.object(financial_model, '_save_cache'),
            patch.object(financial_model, '_fetch_period_safe', return_value=response) as fetch_period,
        ):
            financial_model.build_model('00126380', fs_div='CFS', years=1)
            financial_model.build_model('00126380', fs_div='CFS', years=1)

        self.assertEqual(fetch_period.call_count, 8)


if __name__ == '__main__':
    unittest.main()
