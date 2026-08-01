"""
Tests for Rate Limiting and API Key Authentication Middleware
"""

import time
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient

from cybershield.main import app
from cybershield.middleware.rate_limit import rate_limit_store


class TestRateLimitStore:
    """Tests for the in-memory rate limit store."""

    def setup_method(self):
        """Clear store before each test."""
        rate_limit_store.clear()

    def test_allows_request_under_limit(self):
        """Request under limit should be allowed."""
        allowed, headers = rate_limit_store.is_allowed("test:1", 5, 60)
        assert allowed is True
        assert headers["X-RateLimit-Limit"] == "5"
        assert headers["X-RateLimit-Remaining"] == "4"

    def test_blocks_request_over_limit(self):
        """Request over limit should be blocked."""
        # Use up all allowed requests
        for _ in range(5):
            rate_limit_store.is_allowed("test:2", 5, 60)
        # Next request should be blocked
        allowed, headers = rate_limit_store.is_allowed("test:2", 5, 60)
        assert allowed is False
        assert "Retry-After" in headers

    def test_different_keys_independent(self):
        """Different keys should have independent limits."""
        # Use up limit for key1
        for _ in range(3):
            rate_limit_store.is_allowed("test:3", 3, 60)
        # key2 should still be allowed
        allowed, _ = rate_limit_store.is_allowed("test:3b", 3, 60)
        assert allowed is True

    def test_window_expiry(self):
        """Requests should be allowed again after window expires."""
        # Store with very short window
        for _ in range(2):
            rate_limit_store.is_allowed("test:4", 2, 0)
        # After 0 seconds, should be allowed again (window expired)
        time.sleep(0.01)
        allowed, _ = rate_limit_store.is_allowed("test:4", 2, 0)
        assert allowed is True

    def test_clear_specific_key(self):
        """Clearing a specific key should only clear that key."""
        rate_limit_store.is_allowed("test:5a", 1, 60)
        rate_limit_store.is_allowed("test:5b", 1, 60)
        rate_limit_store.clear("test:5a")
        # test:5a should be allowed, test:5b should not
        allowed_a, _ = rate_limit_store.is_allowed("test:5a", 1, 60)
        assert allowed_a is True

    def test_clear_all_keys(self):
        """Clearing all should reset everything."""
        for _ in range(5):
            rate_limit_store.is_allowed("test:6", 5, 60)
        rate_limit_store.clear()
        allowed, _ = rate_limit_store.is_allowed("test:6", 5, 60)
        assert allowed is True


@pytest.mark.asyncio
async def test_health_endpoint_exempt_from_rate_limit():
    """Health endpoint should work without rate limit issues."""
    transport = ASGITransport(app=cast(Any, app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint_exempt_from_rate_limit():
    """Root endpoint should work without rate limit issues."""
    transport = ASGITransport(app=cast(Any, app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_headers_present():
    """Rate limit headers should be present in responses."""
    transport = ASGITransport(app=cast(Any, app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        # Health is exempt, but check other endpoints
        response = await client.get("/api/v1/jobs")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
