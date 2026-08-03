"""
Unit Tests for the rate limit stores (extended).

Covers the in-memory ``cleanup_expired`` / ``_maybe_cleanup`` branches, the
Redis ``clear`` fallback, and the ``get_rate_limit_store`` factory fallback.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.middleware.rate_limit import (
    RateLimitStore,
    get_rate_limit_store,
)


class TestInMemoryCleanup:
    """Tests for cleanup_expired and _maybe_cleanup."""

    def setup_method(self):
        self.store = RateLimitStore()
        # Force a short cleanup window so entries are considered stale.
        self.store.CLEANUP_WINDOW = 1

    def test_cleanup_expired_removes_stale_keys(self):
        """Should drop keys whose timestamps are all older than the window."""
        now = time.time()
        self.store._requests = {
            "fresh": [now],
            "stale": [now - 100],
            "mixed": [now - 100, now],
            "empty": [],
        }
        removed = self.store.cleanup_expired()
        assert removed == 2  # stale and empty are removed
        assert "fresh" in self.store._requests
        assert "mixed" in self.store._requests
        # stale/empty keys cleaned up
        assert "stale" not in self.store._requests
        assert "empty" not in self.store._requests

    def test_maybe_cleanup_skips_when_not_due(self):
        """Should not clean up when the interval has not elapsed."""
        self.store._last_cleanup = time.time()
        self.store._requests = {"k": [time.time() - 500]}
        with patch.object(self.store, "cleanup_expired") as mock_cleanup:
            self.store._maybe_cleanup()
        mock_cleanup.assert_not_called()

    def test_maybe_cleanup_runs_when_due(self):
        """Should clean up when the interval has elapsed."""
        self.store._last_cleanup = time.time() - self.store.CLEANUP_INTERVAL - 1
        self.store._requests = {"k": [time.time() - 500]}
        self.store._maybe_cleanup()
        assert self.store._requests == {}


class TestGetRateLimitStoreFactory:
    """Tests for the store factory."""

    def test_returns_redis_store_when_configured(self, monkeypatch):
        """Should return a RedisRateLimitStore when REDIS_URL is set."""
        fake_settings = MagicMock()
        fake_settings.redis_url = "redis://localhost:6379"
        fake_store = object()
        with (
            patch("interntrack.config.get_settings", return_value=fake_settings),
            patch(
                "interntrack.middleware.rate_limit.RedisRateLimitStore",
                return_value=fake_store,
            ),
        ):
            result = get_rate_limit_store()
        assert result is fake_store

    def test_falls_back_on_redis_error(self, monkeypatch):
        """Should fall back to the global in-memory store when Redis fails."""
        from interntrack.middleware.rate_limit import rate_limit_store

        fake_settings = MagicMock()
        fake_settings.redis_url = "redis://localhost:6379"
        with (
            patch("interntrack.config.get_settings", return_value=fake_settings),
            patch(
                "interntrack.middleware.rate_limit.RedisRateLimitStore",
                side_effect=RuntimeError("redis down"),
            ),
        ):
            result = get_rate_limit_store()
        assert result is rate_limit_store

    def test_in_memory_when_no_redis_url(self, monkeypatch):
        """Should return the global in-memory store when no URL is configured."""
        from interntrack.middleware.rate_limit import rate_limit_store

        fake_settings = MagicMock()
        fake_settings.redis_url = None
        with patch("interntrack.config.get_settings", return_value=fake_settings):
            result = get_rate_limit_store()
        assert result is rate_limit_store


class TestRedisStoreLazyClient:
    """Tests for the Redis store lazy client creation."""

    @pytest.mark.asyncio
    async def test_get_client_creates_lazily(self):
        """Should import redis and create the client on first access."""
        from interntrack.middleware.rate_limit import RedisRateLimitStore

        store = RedisRateLimitStore("redis://localhost:6379")
        assert store._client is None

        fake_client = AsyncMock()
        with patch("redis.asyncio.from_url", return_value=fake_client) as mock_from_url:
            client = await store._get_client()

        assert client is fake_client
        mock_from_url.assert_called_once()
        # Second call reuses the cached client
        client2 = await store._get_client()
        assert client2 is fake_client
        assert mock_from_url.call_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_expired_returns_zero(self):
        """Redis keys self-expire; cleanup_expired returns 0."""
        from interntrack.middleware.rate_limit import RedisRateLimitStore

        store = RedisRateLimitStore("redis://localhost:6379")
        assert await store.cleanup_expired() == 0


class TestRedisStoreClearFallback:
    """Tests for the Redis store clear fallback."""

    @pytest.mark.asyncio
    async def test_clear_uses_redis_client(self):
        """Should delete the key through the Redis client."""
        from interntrack.middleware.rate_limit import RedisRateLimitStore

        store = RedisRateLimitStore("redis://localhost:6379")
        client = AsyncMock()
        store._client = client  # type: ignore[assignment]

        await store.clear("user-1")
        client.delete.assert_any_await("rl:user-1")
        client.delete.assert_any_await("rl:user-1:seq")

    @pytest.mark.asyncio
    async def test_clear_all_scans_and_deletes(self):
        """Should scan and delete all rl:* keys when no key is given."""
        from interntrack.middleware.rate_limit import RedisRateLimitStore

        store = RedisRateLimitStore("redis://localhost:6379")
        client = AsyncMock()

        async def fake_scan_iter(pattern):
            yield "rl:a"
            yield "rl:b"

        client.scan_iter = fake_scan_iter
        store._client = client  # type: ignore[assignment]

        await store.clear()
        assert client.delete.await_count >= 2

    @pytest.mark.asyncio
    async def test_clear_falls_back_on_error(self):
        """Should delegate to the in-memory fallback when Redis fails."""
        from interntrack.middleware.rate_limit import RedisRateLimitStore

        store = RedisRateLimitStore("redis://localhost:6379")
        store._client = AsyncMock()
        store._client.delete.side_effect = RuntimeError("redis down")

        store._fallback = MagicMock()
        await store.clear("user-1")
        store._fallback.clear.assert_called_once_with("user-1")
