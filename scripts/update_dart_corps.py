#!/usr/bin/env python3
"""Refresh data/dart-corps.json from DART corpCode.xml."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.dart_registry import PACKAGED_CORP_PATH, fetch_live_corp_rows, validate_corp_rows


def main() -> int:
    rows = fetch_live_corp_rows()
    validate_corp_rows(rows)
    PACKAGED_CORP_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(',', ':')) + '\n',
        encoding='utf-8',
    )
    print(f'updated {PACKAGED_CORP_PATH.relative_to(ROOT)} ({len(rows)} rows)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
