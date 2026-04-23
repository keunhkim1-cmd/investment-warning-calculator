from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.naver import stock_code
from lib.validation import normalize_query
from lib.http_utils import safe_traceback, send_json_headers, send_options_response

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self)

    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            name = normalize_query(qs.get('name', [''])[0])
            items = stock_code(name)
            body = json.dumps({'items': items}, ensure_ascii=False).encode()
            self.send_response(200)
        except ValueError as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(400)
        except Exception as e:
            print(f'Error: {safe_traceback()}')
            body = json.dumps({'error': '서버 오류가 발생했습니다.'}, ensure_ascii=False).encode()
            self.send_response(500)
        send_json_headers(self)
        self.end_headers()
        self.wfile.write(body)
