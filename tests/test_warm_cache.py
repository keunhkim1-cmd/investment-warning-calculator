import unittest
from unittest.mock import patch

from lib import warm_cache


class WarmCacheJobTests(unittest.TestCase):
    def test_busy_lock_skips_job(self):
        with patch.object(warm_cache, '_claim_lock', return_value=('busy', '')):
            status, payload = warm_cache.run_warm_cache_job()

        self.assertEqual(status, 202)
        self.assertTrue(payload['skipped'])

    def test_unavailable_lock_runs_tasks(self):
        with (
            patch.object(warm_cache, '_claim_lock', return_value=('unavailable', '')),
            patch.object(warm_cache, 'warm_cache', return_value=[{'ok': True}]),
        ):
            status, payload = warm_cache.run_warm_cache_job()

        self.assertEqual(status, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['lock'], 'unavailable')

    def test_warm_cache_includes_dart_registry_refresh(self):
        with (
            patch.object(warm_cache, 'refresh_durable_corp_rows', return_value={'rows': 1}),
            patch.object(warm_cache, 'search_kind', return_value=[]),
            patch.object(warm_cache, 'search_kind_caution', return_value=[]),
            patch.object(warm_cache, 'market_alert_forecast_payload', return_value={'summary': {'total': 0}}),
            patch.object(warm_cache, 'fetch_prices', return_value=[]),
            patch.object(warm_cache, 'fetch_index_prices', return_value=[]),
            patch.object(warm_cache, 'find_corp_by_stock_code', return_value={'corp_code': '00126380'}),
        ):
            results = warm_cache.warm_cache()

        names = [item['name'] for item in results]
        self.assertIn('dart-corp-registry-refresh', names)
        self.assertNotIn('naver-code-samsung', names)


if __name__ == '__main__':
    unittest.main()
