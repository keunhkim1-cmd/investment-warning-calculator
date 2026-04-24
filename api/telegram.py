"""
투자경고 해제일 계산기 — 텔레그램 봇 (Vercel Webhook)
종목명을 보내면 투자경고/위험 지정일, 해제 예상일, 기준가를 알려줍니다.
"""
from http.server import BaseHTTPRequestHandler
import hmac
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.cache import TTLCache
from lib.http_utils import (
    log_event,
    log_exception,
    safe_exception_text,
    send_text_headers,
)
from lib.telegram_commands import do_caution, do_info, do_search
from lib.telegram_idempotency import claim_update, mark_update_done
from lib.telegram_transport import send_markdown as tg_send, send_plain as tg_send_plain


_seen_updates = TTLCache(ttl=600)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')
MAX_WEBHOOK_BODY_BYTES = _env_int('TELEGRAM_MAX_BODY_BYTES', 64 * 1024)
MAX_UPDATE_AGE_SECONDS = _env_int('TELEGRAM_MAX_UPDATE_AGE_SECONDS', 600)
ADMIN_CHAT_IDS = {
    int(v.strip()) for v in os.environ.get('TELEGRAM_ADMIN_CHAT_IDS', '').split(',')
    if re.fullmatch(r'-?\d+', v.strip())
}


def _is_admin_chat(chat_id: int) -> bool:
    return chat_id in ADMIN_CHAT_IDS


def _is_fresh_update(msg: dict) -> bool:
    """Drop stale Telegram updates to reduce replay and delayed retry abuse."""
    msg_ts = msg.get('date')
    if not isinstance(msg_ts, int):
        return True
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return abs(now_ts - msg_ts) <= MAX_UPDATE_AGE_SECONDS


def _process_update_body(update: dict):
    if not isinstance(update, dict):
        return

    msg = update.get('message') or update.get('edited_message')
    if not msg:
        return
    if not _is_fresh_update(msg):
        return

    chat = msg.get('chat') or {}
    chat_id = chat.get('id')
    if not isinstance(chat_id, int):
        return
    text = msg.get('text', '').strip()

    if not text:
        return

    text = re.sub(r'@\w+', '', text).strip()

    if text.startswith('/start'):
        tg_send(chat_id,
            '📈 *투자경고 해제일 계산기*\n\n'
            '투자경고/위험 종목의 해제 예상일과 기준가를 알려드립니다.\n\n'
            '*명령어*\n'
            '/warning `종목명` — 종목 투자경고 조회\n'
            '/caution `종목명` — 투자경고 지정 예상 점검\n'
            '/bulgunjeon — 불건전 요건 안내\n'
            '/info `종목명` — 사업보고서 요약 (관리자)\n'
            '/help — 사용법 안내\n\n'
            '또는 종목명을 바로 입력해도 됩니다.\n'
            '예: `코셈`, `레이저쎌`')
        return

    if text.startswith('/help') or text.startswith('/도움말'):
        tg_send(chat_id,
            '📖 *사용법*\n\n'
            '*1. 종목 검색*\n'
            '`/warning 종목명` 또는 종목명을 직접 입력\n'
            '예: `/warning 코셈` 또는 `코셈`\n\n'
            '*2. 투자경고 지정 예상*\n'
            '`/caution 종목명` — "투자경고 지정예고" 종목의 실제 지정 여부 점검\n'
            '예: `/caution 코셈`\n'
            'KRX 공식 [1] 또는 [2] 중 하나라도 모두 충족 시 "지정 예상":\n'
            '  \\[1] 단기급등: T/T\\-5 ≥ 160%, 15일 최고, 지수 ×5\n'
            '  \\[2] 중장기급등: T/T\\-15 ≥ 200%, 15일 최고, 지수 ×3\n'
            '지정예고 외 사유(소수계좌 등)는 가격 조건 적용되지 않음\n\n'
            '*3. 불건전 요건 안내*\n'
            '`/bulgunjeon` — KRX 불공정거래 판단 기준 참고용\n\n'
            '*4. 사업보고서 요약*\n'
            '`/info 종목명` — 가장 최근 사업보고서를 10줄로 요약 (관리자 전용)\n'
            '예: `/info 삼성전자`\n\n'
            '*투자경고 해제 조건 안내*\n'
            '아래 3가지 중 하나라도 미해당 시 다음 거래일 해제:\n'
            '① 현재가 ≥ T\\-5 종가의 145%\n'
            '② 현재가 ≥ T\\-15 종가의 175%\n'
            '③ 현재가 ≥ 최근 15일 최고가\n\n'
            '📊 데이터 출처: KRX KIND, 네이버 금융')
        return

    if text.startswith('/warning'):
        query = re.sub(r'^/\S+\s*', '', text).strip()
        do_search(chat_id, query)
        return

    if text.startswith('/info'):
        query = re.sub(r'^/\S+\s*', '', text).strip()
        if not _is_admin_chat(chat_id):
            tg_send_plain(chat_id, '이 명령어는 관리자만 사용할 수 있습니다.')
            return
        try:
            do_info(chat_id, query)
        except Exception as e:
            log_exception('telegram_info_unhandled')
            try:
                tg_send_plain(chat_id, f'❌ 처리 중 오류: {safe_exception_text(e)}')
            except Exception:
                pass
        return

    if text.startswith('/caution'):
        query = re.sub(r'^/\S+\s*', '', text).strip()
        do_caution(chat_id, query)
        return

    if text.startswith('/bulgunjeon'):
        body = (
            '📋 *불건전 요건*\n\n'
            '*1. 5일 or 15일 상승 & 불건전요건*\n'
            '• 최근 5일(15일) 중 전일 대비 주가 상승하고, 특정 계좌(군)이 일중 전체 최고가 매수거래량의 10% 이상 매수일수가 2일(4일) 이상\n'
            '• 최근 5일(15일) 중 특정 계좌(군)의 시세영향력을 고려한 매수관여율이 위원장이 정하는 기준에 해당하는 일수가 2일(4일) 이상\n'
            '• 최근 5일(15일) 중 특정계좌(군)의 시가 또는 종가의 매수관여율이 20% 이상인 일수가 2일(4일) 이상\n'
            '→ 3가지 요건 중 하나에 해당하는 경우\n\n'
            '*2. 1년간 상승 & 불건전요건*\n'
            '• 최근 15일 중 시세영향력을 고려한 매수관여율 상위 10개 계좌의 관여율이 일정 수준 이상인 경우에 해당하는 일수가 4일 이상'
        )
        try:
            tg_send(chat_id, body)
        except Exception:
            tg_send_plain(chat_id, body.replace('*', ''))
        return

    if text.startswith('/web'):
        tg_send(chat_id,
            '🌐 *투자경고 계산기 웹버전*\n'
            'https://shamanism-research.vercel.app/')
        return

    if text.startswith('/'):
        tg_send_plain(chat_id, '알 수 없는 명령어입니다.\n/help 로 사용법을 확인하세요.')
        return

    chat_type = chat.get('type', 'private')
    if chat_type == 'private':
        do_search(chat_id, text)


def process_update(update: dict):
    if not isinstance(update, dict):
        return

    update_id = update.get('update_id')
    local_key = f'upd:{update_id}' if update_id is not None else ''
    claimed = False
    if update_id is not None:
        if _seen_updates.get(local_key):
            return
        if not claim_update(update_id):
            _seen_updates.set(local_key, True)
            return
        _seen_updates.set(local_key, 'processing')
        claimed = True

    try:
        _process_update_body(update)
    except Exception:
        if local_key:
            _seen_updates.delete(local_key)
        raise

    if claimed:
        mark_update_done(update_id)
        _seen_updates.set(local_key, True)


class handler(BaseHTTPRequestHandler):
    def _respond_text(self, status: int, body: bytes):
        self.send_response(status)
        send_text_headers(self, cors=False, cache_control='no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not WEBHOOK_SECRET:
            self._respond_text(503, b'Webhook secret is not configured.')
            return

        token = self.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not hmac.compare_digest(token, WEBHOOK_SECRET):
            self._respond_text(403, b'Forbidden')
            return

        ctype = self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if ctype != 'application/json':
            self._respond_text(415, b'Unsupported Media Type')
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self._respond_text(400, b'Bad Content-Length')
            return

        if length <= 0 or length > MAX_WEBHOOK_BODY_BYTES:
            self._respond_text(413, b'Payload Too Large')
            return

        body = self.rfile.read(length)

        # Vercel Python runtime suspends the function after the HTTP response, so
        # process first and then return 200 OK. update_id dedupe handles retries.
        try:
            update = json.loads(body)
            process_update(update)
        except json.JSONDecodeError:
            self._respond_text(400, b'Invalid JSON')
            return
        except Exception as e:
            log_event('error', 'telegram_update_failed', error=safe_exception_text(e))

        self._respond_text(200, b'OK')

    def do_GET(self):
        status = b'configured' if WEBHOOK_SECRET else b'missing secret'
        self._respond_text(200, b'Telegram bot webhook is ' + status + b'.')

    def log_message(self, *args):
        pass
