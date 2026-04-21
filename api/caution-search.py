from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import caution_search

ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'https://investment-warning-calculator.vercel.app')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = qs.get('name', [''])[0].strip()
        try:
            result = caution_search(name)
            body = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception:
            print(f'Error: {traceback.format_exc()}')
            body = json.dumps(
                {'status': 'error', 'errorMessage': '서버 오류가 발생했습니다.'},
                ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
        self.end_headers()
        self.wfile.write(body)
