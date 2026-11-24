import time
from typing import Any

class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
    def get(self, key: str, ttl: float) -> Any | None:
        entry = self._store.get(key)
        if not entry: return None
        ts, value = entry
        if time.monotonic() - ts > ttl:
            self._store.pop(key, None)
            return None
        return value
    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

market_cache = TTLCache()
