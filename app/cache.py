"""Cache seam — in-process today, Redis tomorrow without rewriting callers."""

from __future__ import annotations

import time
from typing import Any, Protocol


class CacheBackend(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    async def delete(self, key: str) -> None: ...


class MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.time():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class NullCache:
    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None


def build_cache(redis_url: str = "") -> CacheBackend:
    """
    When REDIS_URL is set later, return a Redis-backed implementation here.
    For now we use a small in-process TTL cache (fine for single-node).
    """
    if redis_url:
        # Placeholder for future RedisCache(redis_url)
        return MemoryCache()
    return MemoryCache()
