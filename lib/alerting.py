"""Best-effort Telegram alerts for high-value operational log events."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Mapping


LEVELS = {
    'debug': 10,
    'info': 20,
    'warning': 30,
    'error': 40,
    'critical': 50,
}

DEFAULT_ALERT_EVENTS = frozenset(
    {
        'cache_stale_returned',
        'dart_financial_stale_returned',
        'external_api_call',
        'external_api_retry',
        'financial_dart_fetch_burst',
        'gemini_summary_stale_returned',
        'provider_rate_limit_exceeded',
        'telegram_info_summary_failed',
        'telegram_update_failed',
        'warm_cache_lock_failed',
        'warm_cache_task_failed',
    }
)

COOLDOWN_KEY_FIELDS = (
    'event',
    'provider',
    'cache',
    'task',
    'endpoint',
    'result',
    'status',
    'code',
)

MESSAGE_FIELDS = (
    'provider',
    'cache',
    'task',
    'endpoint',
    'result',
    'status',
    'code',
    'count',
    'limit',
    'retry_after',
    'waited',
    'attempt',
    'delay',
    'url',
    'error',
)

_cooldown_lock = threading.Lock()
_last_alert_at: dict[str, float] = {}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


def _chat_ids() -> tuple[int, ...]:
    raw = (
        os.environ.get('ALERT_TELEGRAM_CHAT_IDS')
        or os.environ.get('ALERT_TELEGRAM_CHAT_ID')
        or os.environ.get('TELEGRAM_ADMIN_CHAT_IDS')
        or ''
    )
    chat_ids: list[int] = []
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            chat_ids.append(int(item))
        except ValueError:
            continue
    return tuple(dict.fromkeys(chat_ids))


def _min_level() -> int:
    raw = os.environ.get('ALERT_TELEGRAM_MIN_LEVEL', 'warning').strip().lower()
    return LEVELS.get(raw, LEVELS['warning'])


def _alert_events() -> frozenset[str]:
    raw = os.environ.get('ALERT_TELEGRAM_EVENTS', '').strip()
    if not raw:
        return DEFAULT_ALERT_EVENTS
    return frozenset(item.strip() for item in raw.split(',') if item.strip())


def _event_level(record: Mapping[str, object]) -> int:
    level = str(record.get('level', '')).strip().lower()
    return LEVELS.get(level, 0)


def _should_alert(record: Mapping[str, object]) -> bool:
    if not _env_bool('ALERT_TELEGRAM_ENABLED', False):
        return False
    if not os.environ.get('TELEGRAM_BOT_TOKEN', '').strip():
        return False
    if not _chat_ids():
        return False
    if _event_level(record) < _min_level():
        return False

    event = str(record.get('event', '')).strip()
    if not event or event.startswith('telegram_alert_'):
        return False
    if event not in _alert_events():
        return False

    provider = str(record.get('provider', '')).strip().lower()
    if provider == 'telegram':
        return False
    if event == 'external_api_call' and str(record.get('result', '')).lower() != 'failure':
        return False
    return True


def _cooldown_seconds() -> int:
    return _env_int('ALERT_TELEGRAM_COOLDOWN_SECONDS', 900, 0, 86400)


def _cooldown_key(record: Mapping[str, object]) -> str:
    parts = []
    for field in COOLDOWN_KEY_FIELDS:
        value = record.get(field)
        if value not in (None, ''):
            parts.append(f'{field}={value}')
    return '|'.join(parts)


def _claim_cooldown(record: Mapping[str, object]) -> bool:
    cooldown = _cooldown_seconds()
    if cooldown <= 0:
        return True

    key = _cooldown_key(record)
    now = time.time()
    with _cooldown_lock:
        last_at = _last_alert_at.get(key, 0)
        if now - last_at < cooldown:
            return False
        _last_alert_at[key] = now
    return True


def _format_alert(record: Mapping[str, object]) -> str:
    level = str(record.get('level', 'warning')).upper()
    event = str(record.get('event', 'unknown'))
    lines = [f'[shamanism alert] {level} {event}']
    for field in MESSAGE_FIELDS:
        value = record.get(field)
        if value not in (None, ''):
            lines.append(f'{field}: {value}')
    return '\n'.join(lines)[:1200]


def _emit_internal_failure(record: Mapping[str, object], exc: Exception) -> None:
    payload = {
        'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'level': 'warning',
        'event': 'telegram_alert_failed',
        'sourceEvent': str(record.get('event', '')),
        'errorType': type(exc).__name__,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def notify_from_log_event(record: Mapping[str, object]) -> None:
    """Send a compact Telegram alert for selected structured log records."""
    if not _should_alert(record):
        return
    if not _claim_cooldown(record):
        return

    text = _format_alert(record)
    try:
        from lib.telegram_transport import send_plain
    except Exception as exc:
        _emit_internal_failure(record, exc)
        return

    for chat_id in _chat_ids():
        try:
            send_plain(chat_id, text)
        except Exception as exc:
            _emit_internal_failure(record, exc)


def _reset_cooldowns_for_tests() -> None:
    with _cooldown_lock:
        _last_alert_at.clear()
