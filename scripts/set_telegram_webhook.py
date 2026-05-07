"""Set or inspect the Telegram webhook for the production bot.

The script reads TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from the
environment, .env.local, or .env without printing secret values.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEBHOOK_URL = 'https://kh-bot.vercel.app/api/telegram'
DEFAULT_ALLOWED_UPDATES = ('message', 'edited_message')


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def load_config_value(name: str) -> str:
    if os.environ.get(name, '').strip():
        return os.environ[name].strip()

    for env_file in (ROOT / '.env.local', ROOT / '.env'):
        value = _parse_env_file(env_file).get(name, '').strip()
        if value:
            return value
    return ''


def telegram_api(token: str, method: str, payload: dict | None = None) -> dict:
    url = f'https://api.telegram.org/bot{token}/{method}'
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def print_webhook_info(info: dict):
    result = info.get('result', {})
    for key in (
        'url',
        'pending_update_count',
        'last_error_date',
        'last_error_message',
        'max_connections',
        'allowed_updates',
    ):
        if key in result:
            print(f'{key}: {result[key]}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Set or inspect the Telegram webhook.')
    parser.add_argument('--url', default=load_config_value('TELEGRAM_WEBHOOK_URL') or DEFAULT_WEBHOOK_URL)
    parser.add_argument('--info', action='store_true', help='Only print current webhook info.')
    parser.add_argument(
        '--drop-pending-updates',
        action='store_true',
        help='Ask Telegram to discard currently queued webhook updates.',
    )
    args = parser.parse_args(argv)

    token = load_config_value('TELEGRAM_BOT_TOKEN')
    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN not found in env, .env.local, or .env')

    if args.info:
        print_webhook_info(telegram_api(token, 'getWebhookInfo'))
        return 0

    secret = load_config_value('TELEGRAM_WEBHOOK_SECRET')
    if not secret:
        raise RuntimeError('TELEGRAM_WEBHOOK_SECRET not found in env, .env.local, or .env')

    payload = {
        'url': args.url,
        'secret_token': secret,
        'allowed_updates': list(DEFAULT_ALLOWED_UPDATES),
    }
    if args.drop_pending_updates:
        payload['drop_pending_updates'] = True

    response = telegram_api(token, 'setWebhook', payload)
    if not response.get('ok'):
        print(f'FAIL: {response}', file=sys.stderr)
        return 1

    print(response.get('description', 'Webhook was set'))
    print_webhook_info(telegram_api(token, 'getWebhookInfo'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
