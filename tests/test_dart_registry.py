import io
import unittest
import zipfile

from lib import dart_registry


class DartRegistryTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
