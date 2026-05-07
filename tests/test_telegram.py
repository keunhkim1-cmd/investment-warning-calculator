import time
import unittest
from unittest.mock import patch

import api.telegram as telegram
import lib.telegram_commands as telegram_commands
from lib.http_client import ExternalAPIError


class TelegramRoutingTests(unittest.TestCase):
    def _message_update(self, text: str, chat_id: int = 100) -> dict:
        return {
            'message': {
                'date': int(time.time()),
                'chat': {'id': chat_id, 'type': 'private'},
                'text': text,
            },
        }

    def test_private_text_routes_to_warning_search(self):
        with patch.object(telegram, 'do_search') as do_search:
            telegram._process_update_body(self._message_update('삼성전자'))

        do_search.assert_called_once_with(100, '삼성전자')

    def test_warning_command_strips_command_prefix(self):
        with patch.object(telegram, 'do_search') as do_search:
            telegram._process_update_body(self._message_update('/warning 코셈'))

        do_search.assert_called_once_with(100, '코셈')

    def test_warning_command_without_query_prompts_for_stock_name(self):
        with patch('lib.telegram_commands.tg_send_plain') as send_plain:
            telegram._process_update_body(self._message_update('/warning'))

        send_plain.assert_called_once_with(100, '종목명을 입력해주세요.\n예: /warning 코셈')

    def test_info_requires_admin_chat(self):
        old_admins = telegram.ADMIN_CHAT_IDS
        telegram.ADMIN_CHAT_IDS = set()
        try:
            with patch.object(telegram, 'tg_send_plain') as send_plain:
                telegram._process_update_body(self._message_update('/info 삼성전자'))
        finally:
            telegram.ADMIN_CHAT_IDS = old_admins

        send_plain.assert_called_once_with(100, '이 명령어는 관리자만 사용할 수 있습니다.')


class TelegramCommandTests(unittest.TestCase):
    def _warning_status(self) -> dict:
        return {
            'status': 'investment_warning',
            'stockCode': '388790',
            'companyName': '라이콤',
            'designationDate': '2026-05-04',
            'nextJudgmentDate': '2026-05-18',
            'releaseConditions': [],
        }

    def test_warning_search_uses_shared_warning_payload_result(self):
        result = {
            'level': '투자경고',
            'stockName': '라이콤',
            'designationDate': '2026-05-04',
            'stockCode': '388790',
        }
        with (
            patch.object(telegram_commands, 'warning_search_payload', return_value={'results': [result]}),
            patch.object(
                telegram_commands,
                'get_investment_warning_status',
                return_value=self._warning_status(),
            ),
            patch.object(telegram_commands, 'tg_send') as send,
            patch.object(telegram_commands, 'tg_send_plain') as send_plain,
        ):
            telegram_commands.do_search(100, '라이콤')

        send.assert_called_once()
        assert '라이콤 투자경고' in send.call_args.args[1]
        assert all('현재 투자경고가 아님' not in call.args[1] for call in send_plain.call_args_list)

    def test_warning_search_empty_shared_payload_sends_not_warning(self):
        with (
            patch.object(telegram_commands, 'warning_search_payload', return_value={'results': []}),
            patch.object(telegram_commands, 'tg_send_plain') as send_plain,
        ):
            telegram_commands.do_search(100, '삼성전자')

        assert any('현재 투자경고가 아님' in call.args[1] for call in send_plain.call_args_list)

    def test_warning_search_exact_name_message_is_forwarded(self):
        with (
            patch.object(
                telegram_commands,
                'warning_search_payload',
                return_value={'results': [], 'message': '정확한 종목명을 입력해주세요.'},
            ),
            patch.object(telegram_commands, 'tg_send_plain') as send_plain,
        ):
            telegram_commands.do_search(100, '라이')

        assert any('정확한 종목명을 입력해주세요.' in call.args[1] for call in send_plain.call_args_list)
        assert all('현재 투자경고가 아님' not in call.args[1] for call in send_plain.call_args_list)

    def test_warning_search_falls_back_to_list_result_when_status_disagrees(self):
        result = {
            'level': '투자경고',
            'stockName': '라이콤',
            'designationDate': '2026-05-04',
            'stockCode': '388790',
        }
        with (
            patch.object(
                telegram_commands,
                'warning_search_payload',
                return_value={'results': [result]},
            ),
            patch.object(
                telegram_commands,
                'get_investment_warning_status',
                return_value={'status': 'not_warning', 'stockCode': '388790'},
            ),
            patch.object(telegram_commands, 'fetch_prices', return_value=[]),
            patch.object(telegram_commands, 'calc_thresholds', return_value={'error': 'price unavailable'}),
            patch.object(telegram_commands, 'tg_send') as send,
            patch.object(telegram_commands, 'tg_send_plain') as send_plain,
        ):
            telegram_commands.do_search(100, '라이콤')

        send.assert_called_once()
        assert '라이콤 투자경고' in send.call_args.args[1]
        assert all('현재 투자경고가 아님' not in call.args[1] for call in send_plain.call_args_list)

    def test_warning_search_list_fallback_skips_detail_retry(self):
        result = {
            'level': '투자경고',
            'stockName': '라이콤',
            'designationDate': '2026-05-04',
            'stockCode': '388790',
            'statusSource': 'krx-list-fallback',
        }
        with (
            patch.object(
                telegram_commands,
                'warning_search_payload',
                return_value={'results': [result]},
            ),
            patch.object(telegram_commands, 'get_investment_warning_status') as get_status,
            patch.object(telegram_commands, 'fetch_prices', return_value=[]),
            patch.object(telegram_commands, 'calc_thresholds', return_value={'error': 'price unavailable'}),
            patch.object(telegram_commands, 'tg_send') as send,
        ):
            telegram_commands.do_search(100, '라이콤')

        get_status.assert_not_called()
        send.assert_called_once()
        assert '라이콤 투자경고' in send.call_args.args[1]

    def test_warning_search_hides_raw_krx_403_message(self):
        error = ExternalAPIError(
            'krx HTTP 403 while requesting https://kind.krx.co.kr/investwarn/investattentwarnrisky.do',
            provider='krx',
            status=403,
            url='https://kind.krx.co.kr/investwarn/investattentwarnrisky.do',
        )
        with (
            patch.object(telegram_commands, 'warning_search_payload', side_effect=error),
            patch.object(telegram_commands, 'tg_send_plain') as send_plain,
        ):
            telegram_commands.do_search(100, '라이콤')

        messages = [call.args[1] for call in send_plain.call_args_list]
        assert any('일시적으로 조회를 제한' in message for message in messages)
        assert all('https://kind.krx.co.kr' not in message for message in messages)


if __name__ == '__main__':
    unittest.main()
