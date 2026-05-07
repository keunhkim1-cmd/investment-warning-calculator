from lib.telegram_messages import build_caution_message, build_investment_warning_status_message


def test_caution_message_empty_result_uses_caution_wording():
    message = build_caution_message({'status': 'not_caution', 'query': '삼성전자'})

    assert message == '"삼성전자" — 현재 투자주의/지정예고 조회 결과가 없습니다.'
    assert '투자경고가 아님' not in message


def test_investment_warning_status_message_explains_future_judgment_date():
    message = build_investment_warning_status_message({
        'status': 'investment_warning',
        'stockCode': '388790',
        'companyName': '라이콤',
        'designationDate': '2026-05-04',
        'nextJudgmentDate': '2026-05-18',
        'expectedReleaseDate': '2026-05-19',
        'calculationBasis': 'KIND 지정 공시 원문 해제요건 기준입니다.',
        'releaseConditions': [
            {
                'type': 'five_day_gain',
                'status': 'unavailable',
                'thresholdPrice': None,
                'evaluationPrice': None,
                'statusReason': 'future_judgment_date',
            },
            {
                'type': 'fifteen_day_gain',
                'status': 'unavailable',
                'thresholdPrice': None,
                'evaluationPrice': None,
                'statusReason': 'future_judgment_date',
            },
            {
                'type': 'fifteen_day_high',
                'status': 'unavailable',
                'thresholdPrice': None,
                'evaluationPrice': None,
                'statusReason': 'future_judgment_date',
            },
        ],
    })

    assert '최초 판단일 (5/18) 전이라 해제 조건 산정 보류' in message
    assert '가격 데이터 문제' not in message


def test_investment_warning_status_message_shows_current_price_preview():
    message = build_investment_warning_status_message({
        'status': 'investment_warning',
        'stockCode': '388790',
        'companyName': '라이콤',
        'designationDate': '2026-05-04',
        'nextJudgmentDate': '2026-05-18',
        'expectedReleaseDate': '2026-05-19',
        'calculationBasis': 'KIND 지정 공시 원문 해제요건 기준입니다.',
        'releaseConditions': [
            {
                'type': 'five_day_gain',
                'status': 'safe',
                'basisDate': '2026-04-28',
                'basisPrice': 5190,
                'thresholdRate': 0.6,
                'thresholdPrice': 8304,
                'evaluationDate': '2026-05-07',
                'evaluationPrice': 5250,
            },
            {
                'type': 'fifteen_day_gain',
                'status': 'safe',
                'basisDate': '2026-04-14',
                'basisPrice': 4200,
                'thresholdRate': 1.0,
                'thresholdPrice': 8400,
                'evaluationDate': '2026-05-07',
                'evaluationPrice': 5250,
            },
            {
                'type': 'fifteen_day_high',
                'status': 'safe',
                'basisDate': '2026-04-23',
                'basisPrice': 5570,
                'thresholdRate': None,
                'thresholdPrice': 5570,
                'evaluationDate': '2026-05-07',
                'evaluationPrice': 5250,
            },
        ],
    })

    assert '🟠 라이콤 투자경고  |  D-12' in message
    assert '현재가  5,250원  (5/7)' in message
    assert '조건      기준가   결과' in message
    assert '① T-5    8,304원   ❌' in message
    assert '② T-15   8,400원   ❌' in message
    assert '현재가 기준 3가지 미해당 · 최종 판단일 5/18 전 예비 산정 🟢' in message
    assert '가격 데이터 문제' not in message
