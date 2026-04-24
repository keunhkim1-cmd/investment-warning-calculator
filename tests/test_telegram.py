import time
import unittest
from unittest.mock import patch

import api.telegram as telegram


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

    def test_info_requires_admin_chat(self):
        old_admins = telegram.ADMIN_CHAT_IDS
        telegram.ADMIN_CHAT_IDS = set()
        try:
            with patch.object(telegram, 'tg_send_plain') as send_plain:
                telegram._process_update_body(self._message_update('/info 삼성전자'))
        finally:
            telegram.ADMIN_CHAT_IDS = old_admins

        send_plain.assert_called_once_with(100, '이 명령어는 관리자만 사용할 수 있습니다.')


if __name__ == '__main__':
    unittest.main()
