from http.server import BaseHTTPRequestHandler
import urllib.parse, urllib.request, json
from xml.etree import ElementTree as ET

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Referer': 'https://finance.naver.com/',
}

def fetch_prices(code, count=20):
    url = (f'https://fchart.stock.naver.com/sise.nhn'
           f'?symbol={code}&timeframe=day&count={count}&requestType=0')
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode('euc-kr', errors='replace')
    root = ET.fromstring(raw)
    prices = []
    for item in root.iter('item'):
        parts = item.get('data', '').split('|')
        if len(parts) < 5 or not parts[4] or parts[4] == '0':
            continue
        d = parts[0]
        prices.append({'date': f'{d[:4]}-{d[4:6]}-{d[6:8]}', 'close': int(parts[4])})
    prices.reverse()   # 최신순
    return prices

def calc_thresholds(prices):
    if len(prices) < 16:
        return {'error': f'데이터 부족 ({len(prices)}일치, 최소 16일 필요)'}
    t_close, t_date     = prices[0]['close'], prices[0]['date']
    t5_close, t5_date   = prices[5]['close'], prices[5]['date']
    t15_close, t15_date = prices[15]['close'], prices[15]['date']
    recent15  = prices[:15]
    max15     = max(p['close'] for p in recent15)
    max15_date = next(p['date'] for p in recent15 if p['close'] == max15)
    thresh1, thresh2, thresh3 = round(t5_close * 1.45), round(t15_close * 1.75), max15
    cond1, cond2, cond3 = t_close >= thresh1, t_close >= thresh2, t_close >= thresh3
    return {
        'tClose': t_close, 'tDate': t_date,
        't5Close': t5_close, 't5Date': t5_date, 'thresh1': thresh1, 'cond1': cond1,
        't15Close': t15_close, 't15Date': t15_date, 'thresh2': thresh2, 'cond2': cond2,
        'max15': max15, 'max15Date': max15_date, 'thresh3': thresh3, 'cond3': cond3,
        'allMet': cond1 and cond2 and cond3,
    }

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = qs.get('code', [''])[0].strip()
        try:
            prices = fetch_prices(code)
            body = json.dumps(
                {'prices': prices[:16], 'thresholds': calc_thresholds(prices)},
                ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
