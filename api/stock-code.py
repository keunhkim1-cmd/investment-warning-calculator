from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import stock_code

ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'https://investment-warning-calculator.vercel.app')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = qs.get('name', [''])[0].strip()
        try:
            items = stock_code(name)
            body = json.dumps({'items': items}, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            print(f'Error: {traceback.format_exc()}')
            body = json.dumps({'error': '서버 오류가 발생했습니다.'}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)
