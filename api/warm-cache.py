"""Scheduled cache warmer for high-fanout public data sources."""
from http.server import BaseHTTPRequestHandler
import hmac
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.http_utils import (
    api_error_payload,
    send_json_response,
)
from lib.warm_cache import run_warm_cache_job


def _authorized(headers) -> tuple[bool, str]:
    expected = os.environ.get('CRON_SECRET', '').strip()
    if not expected:
        return False, 'CRON_SECRET 환경변수가 설정되지 않았습니다.'
    supplied = headers.get('Authorization', '').strip()
    if not hmac.compare_digest(supplied, f'Bearer {expected}'):
        return False, '인증이 필요합니다.'
    return True, ''


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, message = _authorized(self.headers)
        if not ok:
            status = 503 if '설정' in message else 401
            self._respond(status, api_error_payload('AUTH_REQUIRED', message))
            return

        status, payload = run_warm_cache_job()
        self._respond(status, payload)

    def _respond(self, status: int, payload: dict):
        send_json_response(
            self,
            status,
            payload,
            cors=False,
            cache_control='no-store',
        )

    def log_message(self, *args):
        pass
