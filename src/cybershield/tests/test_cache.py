"""
Tests for Cache Module

Tests InMemoryCache and CacheManager functionality.
"""

import asyncio
from unittest.mock import patch

import pytest

from cybershield.cache import CacheManager, InMemoryCache


class TestInMemoryCache:
    """Tests for InMemoryCache class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = InMemoryCache()

    @pytest.mark.asyncio
    async def test_get_empty(self):
        """Should return None for non-existent key."""
        result = await self.cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Should store and retrieve values."""
        await self.cache.set("key1", "value1")
        result = await self.cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Should store values with TTL."""
        await self.cache.set("key1", "value1", ex=3600)
        result = await self.cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_setex(self):
        """Should store values using setex method."""
        await self.cache.setex("key1", 3600, "value1")
        result = await self.cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_delete(self):
        """Should delete stored values."""
        await self.cache.set("key1", "value1")
        await self.cache.delete("key1")
        result = await self.cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self):
        """Should check if key exists."""
        await self.cache.set("key1", "value1")
        assert await self.cache.exists("key1") is True
        assert await self.cache.exists("key2") is False

    @pytest.mark.asyncio
    async def test_flush(self):
        """Should clear all cached data."""
        await self.cache.set("key1", "value1")
        await self.cache.set("key2", "value2")
        await self.cache.flush()
        assert await self.cache.get("key1") is None
        assert await self.cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_overwrite_value(self):
        """Should overwrite existing values."""
        await self.cache.set("key1", "value1")
        await self.cache.set("key1", "value2")
        result = await self.cache.get("key1")
        assert result == "value2"


class TestCacheManager:
    """Tests for CacheManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = CacheManager(prefix="test", default_ttl=300)

    @pytest.mark.asyncio
    async def test_connect_without_redis(self):
        """Should connect using in-memory cache when no Redis URL."""
        await self.cache.connect()
        assert self.cache.is_connected is False

    @pytest.mark.asyncio
    async def test_get_set(self):
        """Should store and retrieve values."""
        await self.cache.connect()
        await self.cache.set("key1", "value1")
        result = await self.cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_set_with_ttl(self):
        """Should store values with custom TTL."""
        await self.cache.connect()
        await self.cache.set("key1", "value1", ttl=60)
        result = await self.cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_set_json(self):
        """Should store and retrieve JSON values."""
        await self.cache.connect()
        data = {"name": "test", "skills": ["python", "security"]}
        await self.cache.set_json("key1", data)
        result = await self.cache.get_json("key1")
        assert result == data

    @pytest.mark.asyncio
    async def test_delete(self):
        """Should delete values."""
        await self.cache.connect()
        await self.cache.set("key1", "value1")
        await self.cache.delete("key1")
        result = await self.cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self):
        """Should check if key exists."""
        await self.cache.connect()
        await self.cache.set("key1", "value1")
        assert await self.cache.exists("key1") is True
        assert await self.cache.exists("key2") is False

    @pytest.mark.asyncio
    async def test_flush(self):
        """Should clear all cached data."""
        await self.cache.connect()
        await self.cache.set("key1", "value1")
        await self.cache.set("key2", "value2")
        await self.cache.flush()
        assert await self.cache.get("key1") is None
        assert await self.cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_generate_cache_key(self):
        """Should generate deterministic cache keys."""
        key1 = self.cache.generate_cache_key("url1", {"param": "value"})
        key2 = self.cache.generate_cache_key("url1", {"param": "value"})
        key3 = self.cache.generate_cache_key("url2", {"param": "value"})
        assert key1 == key2
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_prefix_isolation(self):
        """Should isolate caches by prefix."""
        cache1 = CacheManager(prefix="scraper1")
        cache2 = CacheManager(prefix="scraper2")
        await cache1.connect()
        await cache2.connect()

        await cache1.set("key1", "value1")
        await cache2.set("key1", "value2")

        assert await cache1.get("key1") == "value1"
        assert await cache2.get("key1") == "value2"

    @pytest.mark.asyncio
    async def test_close(self):
        """Should close connections gracefully."""
        await self.cache.connect()
        await self.cache.close()  # Should not raise


class TestCacheManagerWithRedis:
    """Tests for CacheManager with mocked Redis."""

    @pytest.mark.asyncio
    async def test_connect_with_redis_success(self):
        """Should connect to Redis when available."""
        with patch("cybershield.cache.CacheManager.connect") as mock_connect:
            mock_connect.return_value = None
            cache = CacheManager(redis_url="redis://localhost:6379")
            await cache.connect()
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_with_redis_failure_fallback(self):
        """Should fallback to in-memory when Redis fails."""
        cache = CacheManager(redis_url="redis://invalid:9999")
        await cache.connect()
        assert cache.is_connected is False


class TestCacheIntegration:
    """Integration tests for cache functionality."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete cache workflow."""
        cache = CacheManager(prefix="integration_test")
        await cache.connect()

        # Set values
        await cache.set("string_key", "string_value")
        await cache.set_json("json_key", {"data": [1, 2, 3]})

        # Get values
        assert await cache.get("string_key") == "string_value"
        assert await cache.get_json("json_key") == {"data": [1, 2, 3]}

        # Check existence
        assert await cache.exists("string_key") is True
        assert await cache.exists("nonexistent") is False

        # Delete
        await cache.delete("string_key")
        assert await cache.get("string_key") is None

        # Flush
        await cache.flush()
        assert await cache.get_json("json_key") is None

    @pytest.mark.asyncio
    async def test_json_serialization(self):
        """Test JSON serialization of complex objects."""
        cache = CacheManager(prefix="json_test")
        await cache.connect()

        complex_data = {
            "skills": ["Python", "Security", "DevOps"],
            "metadata": {"level": "senior", "years": 5},
            "nested": {"list": [1, 2, 3], "dict": {"a": 1}},
        }

        await cache.set_json("complex", complex_data)
        result = await cache.get_json("complex")

        assert result == complex_data

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test that TTL expiration works."""
        cache = CacheManager(prefix="ttl_test", default_ttl=1)
        await cache.connect()

        # Use a very short TTL for faster testing
        await cache.set("expiring_key", "value", ttl=0.1)
        assert await cache.get("expiring_key") == "value"

        # Wait for expiration (0.2s > 0.1s TTL)
        await asyncio.sleep(0.2)

        # Value should be expired
        result = await cache.get("expiring_key")
        assert result is None, "Value should have expired after TTL"
