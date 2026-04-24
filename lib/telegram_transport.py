"""Telegram Bot API transport helpers."""
import json
import os

from lib.http_client import request_json
from lib.http_utils import telegram_bot_url
from lib.timeouts import TELEGRAM_SEND_TIMEOUT


def bot_token() -> str:
    return os.environ.get('TELEGRAM_BOT_TOKEN', '')


def send_markdown(chat_id: int, text: str, *, token: str | None = None):
    body = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
    }).encode('utf-8')
    return request_json(
        'telegram',
        telegram_bot_url(token if token is not None else bot_token(), 'sendMessage'),
        data=body,
        headers={'Content-Type': 'application/json'},
        timeout=TELEGRAM_SEND_TIMEOUT,
        retries=0,
    )


def send_plain(chat_id: int, text: str, *, token: str | None = None):
    body = json.dumps({'chat_id': chat_id, 'text': text}).encode('utf-8')
    return request_json(
        'telegram',
        telegram_bot_url(token if token is not None else bot_token(), 'sendMessage'),
        data=body,
        headers={'Content-Type': 'application/json'},
        timeout=TELEGRAM_SEND_TIMEOUT,
        retries=0,
    )
