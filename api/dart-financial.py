from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.dart import fetch_financial

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        corp_code = qs.get('corp_code', [''])[0].strip()
        bsns_year = qs.get('bsns_year', [''])[0].strip()
        reprt_code = qs.get('reprt_code', ['11011'])[0].strip()

        try:
            data = fetch_financial(corp_code, bsns_year, reprt_code)
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
