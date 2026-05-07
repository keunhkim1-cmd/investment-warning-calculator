"""Frontend token drift gate.

Fails the gate if any frontend asset (excluding the tokens source-of-truth
``assets/css/base.css``) contains a hardcoded hex color literal. New code must
reference a ``--color-*`` semantic token. Rare unavoidable cases (meta tags,
inline SVG gradient stops) opt out by labeling the line with a
``unify-design:ignore`` comment within the preceding 10 lines.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
IGNORE_MARKER = "unify-design:ignore"
IGNORE_LOOKBACK = 10

EXCLUDED = {REPO_ROOT / "assets" / "css" / "base.css"}


def collect_targets() -> list[Path]:
    targets: list[Path] = []
    targets.extend(sorted((REPO_ROOT / "assets" / "css").glob("*.css")))
    targets.extend(sorted((REPO_ROOT / "assets").glob("*.css")))
    targets.extend(sorted((REPO_ROOT / "assets").glob("*.js")))
    targets.extend(sorted((REPO_ROOT / "assets" / "app").glob("*.js")))
    targets.append(REPO_ROOT / "index.html")
    return [p for p in targets if p.exists() and p not in EXCLUDED]


def violations_in(path: Path) -> list[tuple[int, str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines, start=1):
        match = HEX_RE.search(line)
        if not match:
            continue
        window_start = max(0, idx - 1 - IGNORE_LOOKBACK)
        window = lines[window_start:idx]
        if any(IGNORE_MARKER in w for w in window):
            continue
        out.append((idx, match.group(0), line.strip()))
    return out


def main() -> int:
    findings: list[tuple[Path, int, str, str]] = []
    for path in collect_targets():
        for line_no, hex_value, snippet in violations_in(path):
            findings.append((path, line_no, hex_value, snippet))
    if not findings:
        print("Frontend tokens check passed")
        return 0
    print("Frontend token drift detected:", file=sys.stderr)
    for path, line_no, hex_value, snippet in findings:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{line_no}: {hex_value} -- {snippet}", file=sys.stderr)
    print(
        f"\n{len(findings)} hex literal(s) outside assets/css/base.css. "
        "Use a --color-* token, or label the call site with "
        "'unify-design:ignore' if the hex truly cannot reference a CSS variable.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
