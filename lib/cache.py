"""TTL 기반 인메모리 캐시 (stdlib만 사용)"""
import time
import threading


class TTLCache:
    """스레드 안전한 TTL 캐시. ttl 초 이내 동일 키 요청 시 캐시 반환."""

    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._store: dict = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry and time.time() - entry[1] < self._ttl:
                return entry[0]
            return None

    def set(self, key: str, value):
        with self._lock:
            self._store[key] = (value, time.time())

    def get_or_set(self, key: str, fn):
        """캐시에 있으면 반환, 없으면 fn() 호출 후 저장."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = fn()
        self.set(key, value)
        return value
