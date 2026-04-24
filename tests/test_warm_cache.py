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


if __name__ == '__main__':
    unittest.main()
