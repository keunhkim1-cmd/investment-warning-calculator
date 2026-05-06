from lib import krx


def test_search_kind_fetches_only_investment_warning(monkeypatch):
    calls = []

    def fetch_page(menu_index, *args, **kwargs):
        calls.append(menu_index)
        return f'html-{menu_index}'

    def parse_html(html, level_name):
        return [{
            'level': level_name,
            'stockName': '테스트전자',
            'designationDate': '2026-04-24',
        }]

    monkeypatch.setattr(krx, 'fetch_kind_page', fetch_page)
    monkeypatch.setattr(krx, 'parse_kind_html', parse_html)

    rows = krx.search_kind('')

    assert calls == ['2']
    assert rows == [{
        'level': '투자경고',
        'stockName': '테스트전자',
        'designationDate': '2026-04-24',
    }]
