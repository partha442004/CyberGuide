"""Unit tests for utils/cache.py."""

import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock


class TestInMemoryCache:
    """Tests for InMemoryCache class."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        await cache.set("key1", "value1", ttl=1)
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_expired_key(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        cache._cache["expired"] = {
            "value": "old",
            "expires": time.time() - 1,  # Already expired
        }
        result = await cache.get("expired")
        assert result is None
        assert "expired" not in cache._cache  # Should be cleaned up

    @pytest.mark.asyncio
    async def test_delete(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        await cache.set("key1", "value1")
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        await cache.delete("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_clear(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_set_complex_value(self):
        from interntrack.utils.cache import InMemoryCache

        cache = InMemoryCache()
        complex_val = {"list": [1, 2, 3], "nested": {"key": "value"}}
        await cache.set("complex", complex_val)
        result = await cache.get("complex")
        assert result == complex_val


class TestGetCache:
    """Tests for get_cache function."""

    @patch("interntrack.utils.cache.settings")
    def test_get_cache_returns_inmemory_when_no_redis(self, mock_settings):
        from interntrack.utils.cache import get_cache, InMemoryCache

        mock_settings.redis_url = None
        cache = get_cache()
        assert isinstance(cache, InMemoryCache)

    @patch("interntrack.utils.cache.RedisCache")
    @patch("interntrack.utils.cache.settings")
    def test_get_cache_returns_redis_when_configured(self, mock_settings, mock_redis_cache):
        from interntrack.utils.cache import get_cache

        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_cache.return_value = MagicMock()
        cache = get_cache()
        assert cache == mock_redis_cache.return_value

    @patch("interntrack.utils.cache.RedisCache")
    @patch("interntrack.utils.cache.settings")
    def test_get_cache_fallback_to_inmemory_on_error(self, mock_settings, mock_redis_cache):
        from interntrack.utils.cache import get_cache, InMemoryCache

        mock_settings.redis_url = "redis://invalid:9999"
        mock_redis_cache.side_effect = Exception("Connection refused")
        cache = get_cache()
        assert isinstance(cache, InMemoryCache)


class TestCachedDecorator:
    """Tests for cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_caches_result(self):
        from interntrack.utils.cache import InMemoryCache
        import interntrack.utils.cache as cache_mod

        # Replace global cache with InMemoryCache
        original_cache = cache_mod.cache
        cache_mod.cache = InMemoryCache()

        call_count = 0

        @cache_mod.cached(ttl=300, prefix="test")
        async def my_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        try:
            result1 = await my_function(5)
            result2 = await my_function(5)

            assert result1 == 10
            assert result2 == 10
            assert call_count == 1  # Should only be called once
        finally:
            cache_mod.cache = original_cache

    @pytest.mark.asyncio
    async def test_cached_decorator_different_args(self):
        from interntrack.utils.cache import InMemoryCache
        import interntrack.utils.cache as cache_mod

        original_cache = cache_mod.cache
        cache_mod.cache = InMemoryCache()

        call_count = 0

        @cache_mod.cached(ttl=300, prefix="test")
        async def my_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        try:
            result1 = await my_function(5)
            result2 = await my_function(10)

            assert result1 == 10
            assert result2 == 20
            assert call_count == 2  # Should be called twice
        finally:
            cache_mod.cache = original_cache
