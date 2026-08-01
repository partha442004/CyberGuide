"""
Cache utilities with Redis support.
"""

import json
from functools import wraps
from typing import Any

from interntrack.config import get_settings

settings = get_settings()


class InMemoryCache:
    """Simple in-memory cache (fallback when Redis is unavailable)."""

    def __init__(self):
        self._cache = {}

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        import time

        item = self._cache.get(key)
        if item and item["expires"] > time.time():
            return item["value"]
        if item:
            del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache."""
        import time

        self._cache[key] = {
            "value": value,
            "expires": time.time() + ttl,
        }

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()


class RedisCache:
    """Redis cache implementation."""

    def __init__(self, redis_url: str):
        import redis.asyncio as redis

        self.client = redis.from_url(redis_url)

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache."""
        await self.client.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        await self.client.delete(key)

    async def clear(self) -> None:
        """Clear all cache."""
        await self.client.flushdb()


def get_cache():
    """Get cache instance."""
    if settings.redis_url:
        try:
            return RedisCache(settings.redis_url)
        except Exception:
            pass
    return InMemoryCache()


cache = get_cache()


def cached(ttl: int = 300, prefix: str = ""):
    """Cache decorator."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            key = f"{prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Check cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
