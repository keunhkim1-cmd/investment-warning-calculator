"""Supabase cache client for server-side use only."""
import base64
import json
import os
from supabase import create_client, Client


_client: Client | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _jwt_role(key: str) -> str:
    """Best-effort Supabase key role detection without logging the key."""
    if key.startswith('sb_secret_'):
        return 'service_role'
    if key.startswith('sb_publishable_'):
        return 'anon'

    parts = key.split('.')
    if len(parts) < 2:
        return ''
    payload = parts[1] + '=' * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode('ascii')))
    except Exception:
        return ''
    return str(data.get('role', ''))


def _service_key() -> str:
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
    if key:
        return key

    legacy_key = os.environ.get('SUPABASE_KEY', '').strip()
    if legacy_key and _env_bool('SUPABASE_ALLOW_LEGACY_SERVICE_ROLE_KEY'):
        return legacy_key
    return ''


def cache_enabled() -> bool:
    return bool(os.environ.get('SUPABASE_URL', '').strip() and _service_key())


def cache_writes_enabled() -> bool:
    return _env_bool('SUPABASE_CACHE_WRITES')


def get_client() -> Client:
    """Return a server-only Supabase client.

    Use SUPABASE_SERVICE_ROLE_KEY in Vercel serverless envs. The legacy
    SUPABASE_KEY name is ignored unless SUPABASE_ALLOW_LEGACY_SERVICE_ROLE_KEY
    is explicitly enabled, which prevents accidentally deploying an anon key or
    a service-role key under an ambiguous name.
    """
    global _client
    if _client is None:
        url = os.environ.get('SUPABASE_URL', '').strip()
        key = _service_key()
        if not url or not key:
            raise RuntimeError(
                'SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 설정되지 않았습니다.')

        role = _jwt_role(key)
        if role and role != 'service_role':
            raise RuntimeError('Supabase cache client requires a service-role key.')

        _client = create_client(url, key)
    return _client
