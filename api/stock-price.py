from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os, re, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import fetch_prices, calc_thresholds

ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'https://investment-warning-calculator.vercel.app')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = qs.get('code', [''])[0].strip()
        if not re.match(r'^\d{6}$', code):
            body = json.dumps({'error': '잘못된 종목코드 형식'}, ensure_ascii=False).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            prices = fetch_prices(code)
            body = json.dumps(
                {'prices': prices[:16], 'thresholds': calc_thresholds(prices)},
                ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            print(f'Error: {traceback.format_exc()}')
            body = json.dumps({'error': '서버 오류가 발생했습니다.'}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)
