"""
Tests for the InternTrack rate limiting middleware and store.
"""

import time

import pytest
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from interntrack.middleware.rate_limit import RateLimitMiddleware, rate_limit_store


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


def _build_app(limit: int = 2, api_key_limit: int = 10):
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
    )
    return app


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
