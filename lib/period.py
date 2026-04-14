"""기간(연간/분기) 파생 유틸 — 누적값을 단일 분기로 변환"""

# DART 분기보고서별 누적 기간
# 11012(1Q): 1~3월 누적 = 1Q 단독
# 11014(반기): 1~6월 누적 → 단일 2Q = 반기 - 1Q
# 11013(3Q): 1~9월 누적 → 단일 3Q = 3Q누적 - 반기
# 11011(사업): 1~12월 누적 → 단일 4Q = 사업 - 3Q누적
REPRT_QUARTER = {
    '11012': '1Q',
    '11014': '2Q',
    '11013': '3Q',
    '11011': '4Q',
}

QUARTER_REPRT = {v: k for k, v in REPRT_QUARTER.items()}


def derive_single_quarters(cumulative: dict) -> dict:
    """누적 분기 dict {'1Q': v, '2Q': v, '3Q': v, '4Q': v} → 단일 분기 dict.
    값이 None이면 해당 분기는 None 반환.
    """
    q1 = cumulative.get('1Q')
    h1 = cumulative.get('2Q')  # 1~6월 누적
    q3c = cumulative.get('3Q')  # 1~9월 누적
    fy = cumulative.get('4Q')  # 1~12월 누적

    def _sub(a, b):
        if a is None or b is None:
            return None
        return a - b

    return {
        '1Q': q1,
        '2Q': _sub(h1, q1),
        '3Q': _sub(q3c, h1),
        '4Q': _sub(fy, q3c),
    }


def yoy(cur, prev):
    """전년 대비 증감률. None safe."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev)


def safe_div(num, den):
    if num is None or den is None or den == 0:
        return None
    return num / den
