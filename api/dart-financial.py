from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os, re, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.dart import fetch_financial

ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'https://investment-warning-calculator.vercel.app')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        corp_code = qs.get('corp_code', [''])[0].strip()
        bsns_year = qs.get('bsns_year', [''])[0].strip()
        reprt_code = qs.get('reprt_code', ['11011'])[0].strip()

        if not re.match(r'^\d{8}$', corp_code) or not re.match(r'^\d{4}$', bsns_year):
            body = json.dumps({'error': '잘못된 파라미터 형식'}, ensure_ascii=False).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
            self.end_headers()
            self.wfile.write(body)
            return

        try:
            data = fetch_financial(corp_code, bsns_year, reprt_code)
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            print(f'Error: {traceback.format_exc()}')
            body = json.dumps({'error': '서버 오류가 발생했습니다.'}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)
