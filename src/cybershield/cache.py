"""
Cache Module

Provides caching functionality with Redis backend and in-memory fallback.
- Redis for production (distributed caching)
- In-memory dict for development/testing (no Redis required)
"""

__all__ = ["CacheManager", "cache_manager", "get_cache", "InMemoryCache"]

import json
import hashlib
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Simple in-memory cache fallback when Redis is unavailable."""

    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if key in self._store:
            value, expires_at = self._store[key]
            if expires_at is None or expires_at > time.time():
                return value
            else:
                del self._store[key]
        return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        """Set value with optional expiration in seconds."""
        expires_at = None
        if ex:
            expires_at = time.time() + ex
        self._store[key] = (value, expires_at)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        """Set value with expiration in seconds."""
        await self.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.get(key) is not None

    async def flush(self) -> None:
        """Clear all cached data."""
        self._store.clear()

    async def close(self) -> None:
        """Close connection (no-op for in-memory)."""
        pass


class CacheManager:
    """
    Centralized cache manager with Redis backend and in-memory fallback.

    Features:
    - Automatic fallback to in-memory cache if Redis unavailable
    - JSON serialization for structured data
    - Key prefixing for namespace isolation
    - TTL support for automatic expiration
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: str = "cybershield",
        default_ttl: int = 300,  # 5 minutes
    ):
        self.prefix = prefix
        self.default_ttl = default_ttl
        self._redis_url = redis_url
        self._redis_client = None
        self._memory_cache = InMemoryCache()
        self._use_redis = False

    async def connect(self) -> None:
        """Initialize Redis connection if available."""
        if self._redis_url:
            try:
                import redis.asyncio as aioredis

                client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                # Test connection
                await client.ping()
                self._redis_client = client
                self._use_redis = True
                logger.info(f"Connected to Redis: {self._redis_url}")
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory cache: {e}")
                self._redis_client = None
                self._use_redis = False
        else:
            logger.info("No Redis URL configured, using in-memory cache")
            self._use_redis = False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
        await self._memory_cache.close()

    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        full_key = self._make_key(key)

        if self._use_redis:
            return await self._redis_client.get(full_key)
        return await self._memory_cache.get(full_key)

    async def set(
        self, key: str, value: str, ttl: Optional[int] = None
    ) -> None:
        """Set value with optional TTL."""
        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl

        if self._use_redis:
            await self._redis_client.setex(full_key, ttl, value)
        else:
            await self._memory_cache.set(full_key, value, ex=ttl)

    async def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize JSON value."""
        raw = await self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Serialize and store JSON value."""
        await self.set(key, json.dumps(value), ttl)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        full_key = self._make_key(key)
        if self._use_redis:
            await self._redis_client.delete(full_key)
        else:
            await self._memory_cache.delete(full_key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        full_key = self._make_key(key)
        if self._use_redis:
            return await self._redis_client.exists(full_key) > 0
        return await self._memory_cache.exists(full_key)

    async def flush(self) -> None:
        """Clear all cached data with this prefix."""
        if self._use_redis:
            # Only delete keys with our prefix
            keys = []
            async for key in self._redis_client.scan_iter(f"{self.prefix}:*"):
                keys.append(key)
            if keys:
                await self._redis_client.delete(*keys)
        else:
            await self._memory_cache.flush()

    def generate_cache_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a deterministic cache key from arguments."""
        content = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    @property
    def is_connected(self) -> bool:
        """Check if using Redis."""
        return self._use_redis


# Global cache instance
cache_manager = CacheManager()


async def get_cache() -> CacheManager:
    """Get the global cache manager."""
    return cache_manager
