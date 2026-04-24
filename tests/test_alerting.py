import os
import unittest
from unittest.mock import patch

from lib import alerting
from lib.http_utils import log_event


class TelegramAlertingTests(unittest.TestCase):
    def tearDown(self):
        alerting._reset_cooldowns_for_tests()

    def test_disabled_by_default_even_with_admin_chat_ids(self):
        env = {
            'TELEGRAM_BOT_TOKEN': 'test-token',
            'TELEGRAM_ADMIN_CHAT_IDS': '123',
        }
        with patch.dict(os.environ, env, clear=True):
            with patch('lib.telegram_transport.send_plain') as send_plain:
                alerting.notify_from_log_event(
                    {
                        'level': 'warning',
                        'event': 'provider_rate_limit_exceeded',
                        'provider': 'naver',
                    }
                )

        send_plain.assert_not_called()

    def test_sends_default_high_value_event(self):
        env = {
            'ALERT_TELEGRAM_ENABLED': 'true',
            'ALERT_TELEGRAM_CHAT_IDS': '123,456',
            'ALERT_TELEGRAM_COOLDOWN_SECONDS': '0',
            'TELEGRAM_BOT_TOKEN': 'test-token',
        }
        with patch.dict(os.environ, env, clear=True):
            with patch('lib.telegram_transport.send_plain') as send_plain:
                alerting.notify_from_log_event(
                    {
                        'level': 'warning',
                        'event': 'provider_rate_limit_exceeded',
                        'provider': 'naver',
                        'count': 181,
                        'limit': 180,
                    }
                )

        self.assertEqual(send_plain.call_count, 2)
        self.assertIn('provider_rate_limit_exceeded', send_plain.call_args_list[0].args[1])
        self.assertIn('provider: naver', send_plain.call_args_list[0].args[1])

    def test_uses_admin_chat_ids_when_alert_chat_ids_are_empty(self):
        env = {
            'ALERT_TELEGRAM_ENABLED': 'true',
            'TELEGRAM_ADMIN_CHAT_IDS': '777',
            'TELEGRAM_BOT_TOKEN': 'test-token',
        }
        with patch.dict(os.environ, env, clear=True):
            with patch('lib.telegram_transport.send_plain') as send_plain:
                alerting.notify_from_log_event(
                    {
                        'level': 'error',
                        'event': 'telegram_update_failed',
                        'error': 'boom',
                    }
                )

        send_plain.assert_called_once()
        self.assertEqual(send_plain.call_args.args[0], 777)

    def test_filters_success_and_telegram_provider_events(self):
        env = {
            'ALERT_TELEGRAM_ENABLED': 'true',
            'ALERT_TELEGRAM_CHAT_IDS': '123',
            'TELEGRAM_BOT_TOKEN': 'test-token',
        }
        with patch.dict(os.environ, env, clear=True):
            with patch('lib.telegram_transport.send_plain') as send_plain:
                alerting.notify_from_log_event(
                    {
                        'level': 'info',
                        'event': 'external_api_call',
                        'provider': 'naver',
                        'result': 'success',
                    }
                )
                alerting.notify_from_log_event(
                    {
                        'level': 'warning',
                        'event': 'provider_rate_limit_exceeded',
                        'provider': 'telegram',
                    }
                )

        send_plain.assert_not_called()

    def test_respects_min_level_event_allowlist_and_cooldown(self):
        env = {
            'ALERT_TELEGRAM_ENABLED': 'true',
            'ALERT_TELEGRAM_CHAT_IDS': '123',
            'ALERT_TELEGRAM_EVENTS': 'provider_rate_limit_exceeded',
            'ALERT_TELEGRAM_MIN_LEVEL': 'error',
            'ALERT_TELEGRAM_COOLDOWN_SECONDS': '900',
            'TELEGRAM_BOT_TOKEN': 'test-token',
        }
        with patch.dict(os.environ, env, clear=True):
            with patch('lib.telegram_transport.send_plain') as send_plain:
                alerting.notify_from_log_event(
                    {
                        'level': 'warning',
                        'event': 'provider_rate_limit_exceeded',
                        'provider': 'naver',
                    }
                )
                alerting.notify_from_log_event(
                    {
                        'level': 'error',
                        'event': 'cache_stale_returned',
                        'cache': 'dart',
                    }
                )
                alerting.notify_from_log_event(
                    {
                        'level': 'error',
                        'event': 'provider_rate_limit_exceeded',
                        'provider': 'naver',
                    }
                )
                alerting.notify_from_log_event(
                    {
                        'level': 'error',
                        'event': 'provider_rate_limit_exceeded',
                        'provider': 'naver',
                    }
                )

        send_plain.assert_called_once()

    def test_log_event_triggers_alert_with_redacted_record(self):
        env = {
            'ALERT_TELEGRAM_ENABLED': 'true',
            'ALERT_TELEGRAM_CHAT_IDS': '123',
            'ALERT_TELEGRAM_COOLDOWN_SECONDS': '0',
            'TELEGRAM_BOT_TOKEN': '123456:secret-token',
        }
        with patch.dict(os.environ, env, clear=True):
            with patch('lib.telegram_transport.send_plain') as send_plain:
                log_event(
                    'warning',
                    'provider_rate_limit_exceeded',
                    provider='naver',
                    error='failed https://api.telegram.org/bot123456:secret-token/sendMessage',
                )

        send_plain.assert_called_once()
        self.assertIn('/bot[REDACTED]/sendMessage', send_plain.call_args.args[1])
        self.assertNotIn('123456:secret-token', send_plain.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
