from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.financial_model import build_model
from lib.financial_api_security import auth_error, client_id, rate_limit_error, validate_params
from lib.http_utils import safe_traceback, send_json_headers, send_options_response

ALLOWED_HEADERS = 'Authorization, X-API-Key, X-Financial-Model-Token, Content-Type'


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self, allow_headers=ALLOWED_HEADERS)

    def do_GET(self):
        auth = auth_error(self.headers)
        if auth:
            status, message = auth
            self._respond(status, {'error': message})
            return

        limited = rate_limit_error(client_id(self.headers, getattr(self, 'client_address', None)))
        if limited:
            status, message = limited
            self._respond(status, {'error': message})
            return

        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            corp_code, fs_div, years = validate_params(
                qs.get('corp_code', [''])[0],
                qs.get('fs_div', ['CFS'])[0],
                qs.get('years', ['5'])[0],
            )
        except ValueError:
            self._respond(400, {'error': '잘못된 파라미터 형식'})
            return

        try:
            data = build_model(corp_code, fs_div=fs_div, years=years)
            self._respond(200, data)
        except Exception:
            print(f'Error: {safe_traceback()}')
            self._respond(500, {'error': '서버 오류가 발생했습니다.'})

    def _respond(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self._send_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_headers(self):
        send_json_headers(self, allow_headers=ALLOWED_HEADERS, cache_control='no-store')
