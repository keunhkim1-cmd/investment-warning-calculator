"""
진단용 엔드포인트 — 배포 후 /api/debug 를 브라우저에서 열어 확인
DEBUG_ENABLED=true 환경변수가 설정된 경우에만 동작
"""
from http.server import BaseHTTPRequestHandler
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.http_utils import send_json_headers, send_text_headers

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if os.environ.get('DEBUG_ENABLED', '') != 'true':
            self.send_response(404)
            send_text_headers(self, cors=False, cache_control='no-store')
            self.end_headers()
            return

        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        result = {
            'token_set': bool(token),
            'telegram_api': 'SKIP (token-bearing API check disabled)',
        }

        body = json.dumps(result, ensure_ascii=False, indent=2).encode()
        self.send_response(200)
        send_json_headers(self, cors=False, cache_control='no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
