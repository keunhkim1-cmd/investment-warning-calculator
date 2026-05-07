import io
import unittest
import zipfile
from unittest.mock import patch

from lib import dart_registry, durable_cache


class DartRegistryTests(unittest.TestCase):
    def setUp(self):
        dart_registry._registry_cache.clear()

    def tearDown(self):
        dart_registry._registry_cache.clear()

    def test_parse_corp_code_zip_keeps_listed_companies_only(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>삼성전자</corp_name>
    <stock_code>005930</stock_code>
  </list>
  <list>
    <corp_code>00000000</corp_code>
    <corp_name>비상장</corp_name>
    <stock_code> </stock_code>
  </list>
</result>""".encode('utf-8')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('CORPCODE.xml', xml)

        rows = dart_registry.parse_corp_code_zip(buf.getvalue())

        self.assertEqual(rows, [{'c': '00126380', 'n': '삼성전자', 's': '005930'}])

    def test_resolve_exact_stock_codes_matches_exact_name_only(self):
        rows = [
            {'c': '01569102', 'n': '라이콤', 's': '388790'},
            {'c': '00000001', 'n': '라이콤테스트', 's': '000001'},
        ]
        with patch.object(dart_registry, 'load_corp_rows', return_value=rows):
            self.assertEqual(dart_registry.resolve_exact_stock_codes('라이콤'), [{
                'code': '388790',
                'name': '라이콤',
                'corpCode': '01569102',
            }])
            self.assertEqual(dart_registry.resolve_exact_stock_codes('라이'), [])

    def test_resolve_exact_stock_codes_accepts_direct_code(self):
        self.assertEqual(dart_registry.resolve_exact_stock_codes('005930'), [{
            'code': '005930',
            'name': '',
            'corpCode': '',
        }])

    def test_load_corp_rows_reads_durable_registry_first(self):
        durable_rows = [{'c': '00126380', 'n': '삼성전자', 's': '005930'}]
        with (
            patch.object(dart_registry, '_load_durable_corp_rows', return_value=durable_rows),
            patch.object(dart_registry, 'load_packaged_corp_rows') as packaged,
        ):
            rows = dart_registry.load_corp_rows()

        self.assertEqual(rows, durable_rows)
        packaged.assert_not_called()

    def test_load_corp_rows_falls_back_to_packaged_registry(self):
        packaged_rows = [{'c': '01569102', 'n': '라이콤', 's': '388790'}]
        with (
            patch.object(dart_registry, '_load_durable_corp_rows', return_value=None),
            patch.object(dart_registry, 'load_packaged_corp_rows', return_value=packaged_rows),
        ):
            rows = dart_registry.load_corp_rows()

        self.assertEqual(rows, packaged_rows)

    def test_refresh_durable_corp_rows_stores_valid_registry(self):
        rows = [{'c': '00126380', 'n': '삼성전자', 's': '005930'}]
        with (
            patch.object(dart_registry, 'fetch_live_corp_rows', return_value=rows),
            patch.object(durable_cache, 'enabled', return_value=True),
            patch.object(durable_cache, 'set_json', return_value='OK') as set_json,
        ):
            result = dart_registry.refresh_durable_corp_rows()

        self.assertEqual(result['rows'], 1)
        self.assertTrue(result['stored'])
        set_json.assert_called_once()
        args, kwargs = set_json.call_args
        self.assertEqual(args[0], dart_registry.DART_REGISTRY_CACHE_KEY)
        self.assertEqual(args[1]['rows'], rows)
        self.assertEqual(kwargs['ttl'], dart_registry.DART_REGISTRY_TTL_SECONDS)

    def test_refresh_durable_corp_rows_rejects_empty_registry(self):
        with (
            patch.object(dart_registry, 'fetch_live_corp_rows', return_value=[]),
            patch.object(durable_cache, 'set_json') as set_json,
        ):
            with self.assertRaises(RuntimeError):
                dart_registry.refresh_durable_corp_rows()

        set_json.assert_not_called()


if __name__ == '__main__':
    unittest.main()
