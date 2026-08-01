"""
Tests for the InternTrack rate limiting middleware and stores.

Covers both the in-memory :class:`RateLimitStore` and the Redis-backed
:class:`RedisRateLimitStore` (via fakeredis) plus the store factory and
middleware wiring.
"""

import time

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from interntrack.middleware.rate_limit import (
    RateLimitMiddleware,
    RateLimitStore,
    RedisRateLimitStore,
    get_rate_limit_store,
    rate_limit_store,
)


class TestRateLimitStore:
    """Tests for the in-memory rate limit store."""

    def setup_method(self):
        """Clear store before each test."""
        rate_limit_store.clear()

    def test_allows_request_under_limit(self):
        """Request under limit should be allowed."""
        allowed, headers = rate_limit_store.is_allowed("it:1", 5, 60)
        assert allowed is True
        assert headers["X-RateLimit-Limit"] == "5"
        assert headers["X-RateLimit-Remaining"] == "4"

    def test_blocks_request_over_limit(self):
        """Request over limit should be blocked with Retry-After."""
        for _ in range(5):
            rate_limit_store.is_allowed("it:2", 5, 60)
        allowed, headers = rate_limit_store.is_allowed("it:2", 5, 60)
        assert allowed is False
        assert headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in headers

    def test_different_keys_independent(self):
        """Different keys should have independent limits."""
        for _ in range(3):
            rate_limit_store.is_allowed("it:3", 3, 60)
        allowed, _ = rate_limit_store.is_allowed("it:3b", 3, 60)
        assert allowed is True

    def test_window_expiry(self):
        """Requests should be allowed again after the window expires."""
        for _ in range(2):
            rate_limit_store.is_allowed("it:4", 2, 0)
        time.sleep(0.01)
        allowed, _ = rate_limit_store.is_allowed("it:4", 2, 0)
        assert allowed is True

    def test_clear_specific_key(self):
        """Clearing one key should not affect others."""
        rate_limit_store.is_allowed("it:5a", 1, 60)
        rate_limit_store.is_allowed("it:5b", 1, 60)
        rate_limit_store.clear("it:5a")
        allowed_a, _ = rate_limit_store.is_allowed("it:5a", 1, 60)
        assert allowed_a is True

    def test_clear_all_keys(self):
        """Clearing all keys resets every limit."""
        for _ in range(5):
            rate_limit_store.is_allowed("it:6", 5, 60)
        rate_limit_store.clear()
        allowed, _ = rate_limit_store.is_allowed("it:6", 5, 60)
        assert allowed is True


def _build_app(limit: int = 2, api_key_limit: int = 10, store=None):
    """Build a minimal Starlette app with the rate limit middleware."""

    async def ok(request):
        return JSONResponse({"ok": True})

    app = Starlette(
        routes=[
            Route("/api/v1/test", ok, methods=["GET"]),
            Route("/health", ok, methods=["GET"]),
            Route("/metrics", ok, methods=["GET"]),
            Route("/metrics/prometheus", ok, methods=["GET"]),
        ],
    )
    app.add_middleware(
        RateLimitMiddleware,
        default_limit=limit,
        api_key_limit=api_key_limit,
        store=store,
    )
    return app


class TestRedisRateLimitStore:
    """Tests for the Redis-backed sliding window store (via fakeredis)."""

    @pytest.fixture
    def store(self):
        """A Redis-backed store pointed at a fakeredis server."""
        store = RedisRateLimitStore("redis://localhost:6379/0")
        store._client = FakeRedis()
        return store

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self, store):
        """Requests under the limit are allowed with remaining headers."""
        allowed, headers = await store.is_allowed_async("it:1", 5, 60)
        assert allowed is True
        assert headers["X-RateLimit-Limit"] == "5"
        assert headers["X-RateLimit-Remaining"] == "4"

    @pytest.mark.asyncio
    async def test_blocks_request_over_limit(self, store):
        """Requests over the limit are blocked with Retry-After."""
        for _ in range(5):
            await store.is_allowed_async("it:2", 5, 60)
        allowed, headers = await store.is_allowed_async("it:2", 5, 60)
        assert allowed is False
        assert headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in headers

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, store):
        """Different keys have independent limits."""
        for _ in range(3):
            await store.is_allowed_async("it:3", 3, 60)
        allowed, _ = await store.is_allowed_async("it:3b", 3, 60)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_window_expiry(self, store):
        """Requests are allowed again after the window expires."""
        for _ in range(2):
            await store.is_allowed_async("it:4", 2, 0)
        time.sleep(0.01)
        allowed, _ = await store.is_allowed_async("it:4", 2, 0)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_clear_specific_key(self, store):
        """Clearing one key does not affect others."""
        await store.is_allowed_async("it:5a", 1, 60)
        await store.is_allowed_async("it:5b", 1, 60)
        await store.clear("it:5a")
        allowed_a, _ = await store.is_allowed_async("it:5a", 1, 60)
        assert allowed_a is True

    @pytest.mark.asyncio
    async def test_clear_all_keys(self, store):
        """Clearing all keys resets every limit."""
        for _ in range(5):
            await store.is_allowed_async("it:6", 5, 60)
        await store.clear()
        allowed, _ = await store.is_allowed_async("it:6", 5, 60)
        assert allowed is True


class TestRedisRateLimitStoreFallback:
    """Tests for the graceful degradation when Redis is unreachable."""

    @pytest.mark.asyncio
    async def test_falls_back_to_in_memory_when_redis_down(self):
        """A Redis outage degrades to the in-memory store, not a 500."""

        class _BrokenRedis:
            """Fake client whose every command raises ConnectionError."""

            async def eval(self, *args, **kwargs):
                raise ConnectionError("connection refused")

        store = RedisRateLimitStore("redis://localhost:6379/0")
        store._client = _BrokenRedis()

        allowed, headers = await store.is_allowed_async("it:9", 5, 60)
        assert allowed is True
        assert headers["X-RateLimit-Remaining"] == "4"

    @pytest.mark.asyncio
    async def test_fallback_clears_in_memory(self):
        """clear() degrades to the in-memory fallback on Redis failure."""

        class _BrokenRedis:
            async def scan_iter(self, *args, **kwargs):
                raise ConnectionError("connection refused")

        store = RedisRateLimitStore("redis://localhost:6379/0")
        store._client = _BrokenRedis()
        # Should not raise
        await store.clear()


class TestRateLimitStoreAsyncAlias:
    """The async alias on the in-memory store matches the sync result."""

    @pytest.mark.asyncio
    async def test_is_allowed_async_matches_sync(self):
        """is_allowed_async produces the same result as is_allowed."""
        # Separate stores: calling both methods on one store would double-count.
        # Compare only the stable fields (X-RateLimit-Reset is a wall-clock
        # timestamp and can straddle a second boundary between the two calls).
        sync_store = RateLimitStore()
        async_store = RateLimitStore()
        sync_result = sync_store.is_allowed("it:10", 5, 60)
        async_result = await async_store.is_allowed_async("it:10", 5, 60)
        assert sync_result[0] == async_result[0]
        assert (
            sync_result[1]["X-RateLimit-Limit"] == async_result[1]["X-RateLimit-Limit"]
        )
        assert (
            sync_result[1]["X-RateLimit-Remaining"]
            == async_result[1]["X-RateLimit-Remaining"]
        )


class TestGetRateLimitStore:
    """Tests for the store factory selection."""

    @pytest.mark.asyncio
    async def test_redis_store_used_when_redis_url_configured(self, monkeypatch):
        """REDIS_URL configured -> Redis-backed store."""
        # get_rate_limit_store() imports get_settings lazily, so patch the
        # source module attribute.
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: type("S", (), {"redis_url": "redis://localhost:6379/0"})(),
        )
        store = get_rate_limit_store()
        assert isinstance(store, RedisRateLimitStore)

    @pytest.mark.asyncio
    async def test_in_memory_used_without_redis_url(self, monkeypatch):
        """No REDIS_URL -> the global in-memory store."""
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: type("S", (), {"redis_url": None})(),
        )
        assert get_rate_limit_store() is rate_limit_store


class TestRateLimitMiddleware:
    """Tests for rate limiting over HTTP."""

    def setup_method(self):
        """Clear store before each test."""
        rate_limit_store.clear()

    @pytest.mark.asyncio
    async def test_blocks_after_limit_with_error_contract(self):
        """429 responses use the InternTrack error contract and headers."""
        transport = ASGITransport(app=_build_app(limit=2))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/v1/test")
            second = await client.get("/api/v1/test")
            blocked = await client.get("/api/v1/test")

        assert first.status_code == 200
        assert first.headers["X-RateLimit-Limit"] == "2"
        assert second.status_code == 200
        assert blocked.status_code == 429

        data = blocked.json()
        assert data["error"]["code"] == "RATE_LIMITED"
        assert data["error"]["message"]
        assert data["error"]["details"] == {}
        assert "Retry-After" in blocked.headers
        assert blocked.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_exempt_paths_bypass_rate_limit(self):
        """Health and docs paths are exempt from rate limiting."""
        transport = ASGITransport(app=_build_app(limit=1))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Exempt paths should always succeed even past the limit
            for _ in range(5):
                response = await client.get("/health")
            assert response.status_code == 200
            # /metrics (monitoring) must also bypass the rate limit so
            # scrapers stay reliable.
            for _ in range(5):
                response = await client.get("/metrics")
            assert response.status_code == 200
            # /metrics/prometheus (scrape target) is exempt too.
            for _ in range(5):
                response = await client.get("/metrics/prometheus")
            assert response.status_code == 200
            # Exempt requests never count: the first limited-route request is
            # allowed and only the second is blocked (limit=1).
            first = await client.get("/api/v1/test")
            blocked = await client.get("/api/v1/test")
            assert first.status_code == 200
            assert blocked.status_code == 429

    @pytest.mark.asyncio
    async def test_api_key_gets_higher_limit(self):
        """Requests with an API key use the api-key limit."""
        transport = ASGITransport(app=_build_app(limit=2, api_key_limit=5))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(5):
                response = await client.get(
                    "/api/v1/test",
                    headers={"X-API-Key": "test-key-123"},
                )

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_429_response_includes_cors_headers(self):
        """Rate-limited responses still pass through CORS (middleware order)."""
        app = _build_app(limit=1)
        # Mirror main.py wiring: CORS registered after (wraps) the rate limiter.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/v1/test")
            blocked = await client.get(
                "/api/v1/test",
                headers={"Origin": "http://localhost:3000"},
            )

        assert first.status_code == 200
        assert blocked.status_code == 429
        assert blocked.headers.get("access-control-allow-origin") == "*"

    @pytest.mark.asyncio
    async def test_middleware_with_redis_store(self):
        """The middleware works end-to-end against a Redis-backed store."""
        store = RedisRateLimitStore("redis://localhost:6379/0")
        store._client = FakeRedis()
        transport = ASGITransport(app=_build_app(limit=2, store=store))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/v1/test")
            second = await client.get("/api/v1/test")
            blocked = await client.get("/api/v1/test")

        assert first.status_code == 200
        assert second.status_code == 200
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"
