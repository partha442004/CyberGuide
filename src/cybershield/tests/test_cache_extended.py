"""
Unit Tests for Cache Module (extended)

Covers the remaining Redis-backed paths of ``cybershield/cache.py``:
- Successful Redis connection (connect success branch)
- get/set/delete/exists/flush through the Redis client
- JSON decode error fallback
- Global ``get_cache`` accessor
"""

from unittest.mock import patch

import pytest

from cybershield.cache import CacheManager, cache_manager, get_cache


class FakeRedisClient:
    """A minimal fake redis.asyncio client for testing Redis paths."""

    def __init__(self):
        self._store = {}
        self.ping_called = 0
        self.closed = False

    async def ping(self):
        self.ping_called += 1
        return True

    async def get(self, key):
        return self._store.get(key)

    async def setex(self, key, ttl, value):
        self._store[key] = value

    async def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)

    async def exists(self, key):
        return 1 if key in self._store else 0

    async def scan_iter(self, pattern):
        for key in list(self._store):
            if pattern.rstrip("*") in key:
                yield key

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_aioredis():
    """Patch redis.asyncio.from_url to return a fresh fake client."""

    client = FakeRedisClient()
    with patch("redis.asyncio.from_url", return_value=client):
        yield client


class TestCacheManagerRedisPath:
    """Tests exercising the Redis-backed branches of CacheManager."""

    @pytest.mark.asyncio
    async def test_connect_success_uses_redis(self, fake_aioredis):
        """Should set _use_redis when ping succeeds."""
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        assert cache.is_connected is True
        assert fake_aioredis.ping_called == 1

    @pytest.mark.asyncio
    async def test_get_uses_redis_client(self, fake_aioredis):
        """Should read through the Redis client when connected."""
        fake_aioredis._store["cybershield:key1"] = "value1"
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        assert await cache.get("key1") == "value1"
        assert await cache.get("missing") is None

    @pytest.mark.asyncio
    async def test_set_uses_redis_setex(self, fake_aioredis):
        """Should write through Redis setex with TTL."""
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        await cache.set("key1", "value1", ttl=60)
        assert fake_aioredis._store["cybershield:key1"] == "value1"

    @pytest.mark.asyncio
    async def test_delete_uses_redis_client(self, fake_aioredis):
        """Should delete through the Redis client."""
        fake_aioredis._store["cybershield:key1"] = "value1"
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        await cache.delete("key1")
        assert "cybershield:key1" not in fake_aioredis._store

    @pytest.mark.asyncio
    async def test_exists_uses_redis_client(self, fake_aioredis):
        """Should check existence through the Redis client."""
        fake_aioredis._store["cybershield:key1"] = "value1"
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        assert await cache.exists("key1") is True
        assert await cache.exists("missing") is False

    @pytest.mark.asyncio
    async def test_flush_scans_and_deletes_prefixed_keys(self, fake_aioredis):
        """Should scan only prefixed keys and delete them."""
        fake_aioredis._store["cybershield:a"] = "1"
        fake_aioredis._store["cybershield:b"] = "2"
        fake_aioredis._store["other:c"] = "3"
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        await cache.flush()
        assert fake_aioredis._store == {"other:c": "3"}

    @pytest.mark.asyncio
    async def test_close_closes_redis_client(self, fake_aioredis):
        """Should close the Redis client and memory cache."""
        cache = CacheManager(redis_url="redis://localhost:6379")
        await cache.connect()
        await cache.close()
        assert fake_aioredis.closed is True


class TestGetJsonDecodeError:
    """Tests for the JSON decode error fallback."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self, monkeypatch):
        """Should return None when stored JSON is malformed."""
        cache = CacheManager(prefix="test")
        await cache.connect()
        await cache.set("bad", "{not-json")
        assert await cache.get_json("bad") is None

    @pytest.mark.asyncio
    async def test_empty_raw_returns_none(self):
        """Should return None when no value is stored."""
        cache = CacheManager(prefix="test")
        await cache.connect()
        assert await cache.get_json("missing") is None


class TestGetCacheAccessor:
    """Tests for the module-level get_cache accessor."""

    @pytest.mark.asyncio
    async def test_returns_global_cache_manager(self):
        """Should return the global cache manager instance."""
        assert await get_cache() is cache_manager
