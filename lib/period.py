"""기간(연간/분기) 파생 유틸"""

# DART reprt_code → 분기 매핑 (DART Open API 표준)
# 11013: 1분기보고서, 11012: 반기보고서, 11014: 3분기보고서, 11011: 사업보고서
# fnlttSinglAcntAll의 thstrm_amount:
#  - 11013/11012/11014 (분기): 당분기(3개월) 단일 값
#  - 11011 (사업): 당기(12개월) 누계값
#  → Q4 = 사업 - (Q1+Q2+Q3), BS는 시점값이라 각 보고서의 시점값 그대로 사용
REPRT_QUARTER = {
    '11013': '1Q',
    '11012': '2Q',
    '11014': '3Q',
    '11011': 'FY',  # 사업보고서는 연간 합계
}

QUARTER_REPRT = {v: k for k, v in REPRT_QUARTER.items()}


def derive_q4_from_annual(q1, q2, q3, fy):
    """단일 분기 IS/CF 값들에서 Q4 도출. Q4 = FY - (Q1+Q2+Q3)."""
    if fy is None:
        return None
    parts = [q1, q2, q3]
    if any(p is None for p in parts):
        return None
    return fy - (q1 + q2 + q3)


def yoy(cur, prev):
    """전년 대비 증감률. None safe."""
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev)


def safe_div(num, den):
    if num is None or den is None or den == 0:
        return None
    return num / den
