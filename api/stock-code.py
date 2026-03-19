from http.server import BaseHTTPRequestHandler
import urllib.parse, urllib.request, json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = qs.get('name', [''])[0].strip()
        try:
            params = urllib.parse.urlencode({'q': name, 'target': 'stock'})
            req = urllib.request.Request(
                f'https://ac.stock.naver.com/ac?{params}', headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode('utf-8'))
            items = [{'code': it['code'], 'name': it['name'],
                      'market': it.get('typeName', '')}
                     for it in data.get('items', [])]
            body = json.dumps({'items': items}, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
