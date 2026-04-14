"""간단한 재시도 유틸 (stdlib만 사용) — 지수 백오프"""
import time
import random


def retry(fn, retries=2, base_delay=0.5):
    """fn()을 최대 retries+1회 시도. 실패 시 지수 백오프(+jitter) 후 재시도."""
    for i in range(retries + 1):
        try:
            return fn()
        except Exception:
            if i == retries:
                raise
            delay = base_delay * (2 ** i) + random.uniform(0, 0.3)
            time.sleep(delay)
