from http.server import BaseHTTPRequestHandler
import urllib.parse, urllib.request, re, json
from datetime import date, timedelta

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://kind.krx.co.kr/',
}

def fetch_kind_page(menu_index, page=1):
    end_date   = date.today().strftime('%Y%m%d')
    start_date = (date.today() - timedelta(days=365)).strftime('%Y%m%d')
    params = urllib.parse.urlencode({
        'method': 'investattentwarnriskySub', 'menuIndex': menu_index,
        'marketType': '', 'searchCorpName': '',
        'startDate': start_date, 'endDate': end_date,
        'pageIndex': str(page), 'currentPageSize': '100',
        'orderMode': '3', 'orderStat': 'D',
    })
    req = urllib.request.Request(
        f'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do?{params}',
        headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        return r.read().decode('utf-8', errors='replace')

def parse_kind_html(html, level_name):
    results = []
    tbody_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
    if not tbody_m:
        return results
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_m.group(1), re.DOTALL):
        name_m = re.search(r'<td\s+title="([^"]+)"', row)
        if not name_m or not name_m.group(1).strip():
            continue
        dates = re.findall(
            r'<td[^>]*class="[^"]*txc[^"]*"[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</td>', row)
        if not dates:
            continue
        results.append({'level': level_name, 'stockName': name_m.group(1).strip(),
                        'designationDate': dates[0]})
    return results

def search_kind(stock_name):
    all_results = []
    for idx, level in [('2', '투자경고'), ('3', '투자위험')]:
        try:
            rows = parse_kind_html(fetch_kind_page(idx), level)
            if stock_name:
                rows = [r for r in rows if stock_name in r['stockName']]
            all_results.extend(rows)
        except Exception as e:
            print(f'KIND error menu={idx}: {e}')
    all_results.sort(key=lambda x: x.get('designationDate', ''), reverse=True)
    return all_results

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs   = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = qs.get('name', [''])[0].strip()
        try:
            results = search_kind(name)
            body = json.dumps({'results': results, 'query': name}, ensure_ascii=False).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({'error': str(e)}, ensure_ascii=False).encode()
            self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
