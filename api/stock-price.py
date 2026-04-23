from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import fetch_prices, calc_thresholds
from lib.validation import validate_stock_code
from lib.http_utils import safe_traceback, send_json_headers, send_options_response

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self)

    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            code = validate_stock_code(qs.get('code', [''])[0])
        except ValueError as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(400)
            send_json_headers(self)
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            prices = fetch_prices(code)
            body = json.dumps(
                {'prices': prices[-16:], 'thresholds': calc_thresholds(prices)},
                ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            print(f'Error: {safe_traceback()}')
            body = json.dumps({'error': '서버 오류가 발생했습니다.'}, ensure_ascii=False).encode()
            self.send_response(500)
        send_json_headers(self)
        self.end_headers()
        self.wfile.write(body)
