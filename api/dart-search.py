from http.server import BaseHTTPRequestHandler
import urllib.parse, json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.dart import search_disclosure

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        corp_code = qs.get('corp_code', [''])[0].strip()
        bgn_de = qs.get('bgn_de', [''])[0].strip()
        end_de = qs.get('end_de', [''])[0].strip()
        page_no = qs.get('page_no', ['1'])[0].strip()
        page_count = qs.get('page_count', ['20'])[0].strip()
        pblntf_ty = qs.get('pblntf_ty', [''])[0].strip()

        try:
            data = search_disclosure(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
                page_no=int(page_no),
                page_count=int(page_count),
                pblntf_ty=pblntf_ty,
            )
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
