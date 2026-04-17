"""Google Gemini API 호출 (stdlib only)"""
import urllib.request, urllib.parse, json, os

from lib.retry import retry

GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta'
DEFAULT_MODEL = 'gemini-2.5-flash'


def _api_key() -> str:
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise ValueError('GEMINI_API_KEY 환경변수가 설정되지 않았습니다.')
    return key


def generate(prompt: str, model: str = DEFAULT_MODEL, max_output_tokens: int = 1024) -> str:
    """Gemini generateContent — 단일 프롬프트 → 텍스트 응답."""
    url = f'{GEMINI_BASE}/models/{model}:generateContent?key={_api_key()}'
    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.3,
            'maxOutputTokens': max_output_tokens,
        },
    }).encode('utf-8')

    def _call():
        req = urllib.request.Request(
            url, data=body,
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))

    data = retry(_call)
    candidates = data.get('candidates') or []
    if not candidates:
        raise RuntimeError(f'Gemini 응답에 candidates 없음: {data}')
    parts = candidates[0].get('content', {}).get('parts') or []
    return ''.join(p.get('text', '') for p in parts).strip()
