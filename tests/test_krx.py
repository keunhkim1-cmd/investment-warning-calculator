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


def test_search_kind_filters_case_insensitively(monkeypatch):
    monkeypatch.setattr(krx, 'fetch_kind_page', lambda menu_index, *args, **kwargs: 'html')
    monkeypatch.setattr(krx, 'parse_kind_html', lambda html, level_name: [
        {
            'level': level_name,
            'stockName': '원익IPS',
            'designationDate': '2026-04-24',
            'stockCode': '240810',
        },
        {
            'level': level_name,
            'stockName': '다른전자',
            'designationDate': '2026-04-24',
            'stockCode': '000001',
        },
    ])

    rows = krx.search_kind('원익ips')

    assert rows == [{
        'level': '투자경고',
        'stockName': '원익IPS',
        'designationDate': '2026-04-24',
        'stockCode': '240810',
    }]


def test_search_kind_caution_filters_case_insensitively(monkeypatch):
    html = '''
      <table><tbody>
        <tr class="icn_t_ko">
          <td>1</td>
          <td title="SK하이닉스">
            <a onclick="companysummary_open('000660')">SK하이닉스</a>
          </td>
          <td>투자경고 지정예고</td>
          <td class="txc">2026-05-04</td>
        </tr>
      </tbody></table>
    '''
    monkeypatch.setattr(krx, 'fetch_kind_page', lambda menu_index, *args, **kwargs: html)

    rows = krx.search_kind_caution('sk하이닉스')

    assert len(rows) == 1
    assert rows[0]['stockName'] == 'SK하이닉스'
    assert rows[0]['latestDesignationDate'] == '2026-05-04'
    assert rows[0]['latestDesignationReason'] == '투자경고 지정예고'
