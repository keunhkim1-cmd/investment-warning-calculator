from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os, re, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.financial_model import build_model

ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'https://investment-warning-calculator.vercel.app')


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        corp_code = qs.get('corp_code', [''])[0].strip()
        fs_div = qs.get('fs_div', ['CFS'])[0].strip().upper()
        try:
            years = max(2, min(7, int(qs.get('years', ['5'])[0])))
        except ValueError:
            years = 5

        if not re.match(r'^\d{8}$', corp_code) or fs_div not in ('CFS', 'OFS'):
            self._respond(400, {'error': '잘못된 파라미터 형식'})
            return

        try:
            data = build_model(corp_code, fs_div=fs_div, years=years)
            self._respond(200, data)
        except Exception:
            print(f'Error: {traceback.format_exc()}')
            self._respond(500, {'error': '서버 오류가 발생했습니다.'})

    def _respond(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)
