"""Unit tests for utils/cache.py."""

import time
from unittest.mock import patch

import pytest

from interntrack.utils.cache import InMemoryCache, cached, get_cache


class TestInMemoryCache:
    """Tests for InMemoryCache."""

    @pytest.fixture
    def cache(self):
        return InMemoryCache()

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        await cache.set("key1", "value1", ttl=60)
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired_key(self, cache):
        await cache.set("key1", "value1", ttl=0)
        time.sleep(0.01)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        await cache.set("key1", "value1")
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        await cache.delete("nonexistent")
        assert await cache.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_set_different_ttl(self, cache):
        await cache.set("key1", "value1", ttl=1)
        await cache.set("key2", "value2", ttl=3600)
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"


class TestCachedDecorator:
    """Tests for cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_caches_result(self):
        call_count = 0
        mock_cache = InMemoryCache()

        with patch("interntrack.utils.cache.cache", mock_cache):

            @cached(ttl=60, prefix="test")
            async def my_func(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            result1 = await my_func(5)
            result2 = await my_func(5)

            assert result1 == 10
            assert result2 == 10
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_different_args(self):
        call_count = 0
        mock_cache = InMemoryCache()

        with patch("interntrack.utils.cache.cache", mock_cache):

            @cached(ttl=60, prefix="test")
            async def my_func(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            await my_func(5)
            await my_func(6)

            assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_preserves_function_name(self):
        mock_cache = InMemoryCache()

        with patch("interntrack.utils.cache.cache", mock_cache):

            @cached(ttl=60, prefix="test")
            async def my_function():
                pass

            assert my_function.__name__ == "my_function"


class TestGetCache:
    """Tests for get_cache function."""

    def test_returns_in_memory_when_no_redis(self):
        with patch("interntrack.utils.cache.settings") as mock_settings:
            mock_settings.redis_url = None
            cache_instance = get_cache()
            assert isinstance(cache_instance, InMemoryCache)

    def test_returns_in_memory_when_redis_fails(self):
        with (
            patch("interntrack.utils.cache.settings") as mock_settings,
            patch(
                "interntrack.utils.cache.RedisCache",
                side_effect=Exception("Connection failed"),
            ),
        ):
            mock_settings.redis_url = "redis://invalid:9999"
            cache_instance = get_cache()
            assert isinstance(cache_instance, InMemoryCache)
