from http.server import BaseHTTPRequestHandler
import urllib.parse, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.financial_api_security import auth_error, client_id, rate_limit_error
from lib.http_utils import (
    api_error_payload,
    api_success_payload,
    log_exception,
    send_json_response,
    send_options_response,
)
from lib.usecases import financial_model_payload

ALLOWED_HEADERS = 'Authorization, X-API-Key, X-Financial-Model-Token, Content-Type'


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self, allow_headers=ALLOWED_HEADERS)

    def do_GET(self):
        auth = auth_error(self.headers)
        if auth:
            status, message = auth
            code = 'ENDPOINT_NOT_CONFIGURED' if status == 503 else 'AUTH_REQUIRED'
            self._respond(status, api_error_payload(code, message))
            return

        limited = rate_limit_error(client_id(self.headers, getattr(self, 'client_address', None)))
        if limited:
            status, message = limited
            self._respond(status, api_error_payload('RATE_LIMITED', message))
            return

        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            data = financial_model_payload(
                corp_code=qs.get('corp_code', [''])[0],
                fs_div=qs.get('fs_div', ['CFS'])[0],
                years=qs.get('years', ['5'])[0],
            )
            self._respond(200, api_success_payload(data))
        except ValueError:
            self._respond(
                400,
                api_error_payload('VALIDATION_ERROR', '잘못된 파라미터 형식'),
            )
            return
        except Exception:
            log_exception('api_request_failed', endpoint='financial-model')
            self._respond(
                500,
                api_error_payload('INTERNAL_ERROR', '서버 오류가 발생했습니다.'),
            )

    def _respond(self, status: int, payload: dict):
        send_json_response(
            self,
            status,
            payload,
            allow_headers=ALLOWED_HEADERS,
            cache_control='no-store',
        )
