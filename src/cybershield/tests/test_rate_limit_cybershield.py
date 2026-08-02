"""
Unit tests for cybershield.middleware.rate_limit.

Covers the RateLimitStore cleanup paths (cleanup_expired, _maybe_cleanup,
clear) and the RateLimitMiddleware dispatch branches (exempt paths, API
key keys, IP keys, 429 responses, header injection).
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from cybershield.middleware.rate_limit import (
    RateLimitMiddleware,
    RateLimitStore,
    rate_limit_store,
)


class TestRateLimitStoreCleanup:
    def setup_method(self):
        rate_limit_store.clear()

    def test_cleanup_expired_removes_old_entries(self):
        store = RateLimitStore()
        old = time.time() - store.CLEANUP_WINDOW - 100
        store._requests["k1"] = [old]
        store._requests["k2"] = [time.time()]
        removed = store.cleanup_expired()
        assert removed == 1
        assert "k1" not in store._requests
        assert "k2" in store._requests

    def test_cleanup_expired_updates_last_cleanup(self):
        store = RateLimitStore()
        store._last_cleanup = time.time() - 1000
        store.cleanup_expired()
        assert time.time() - store._last_cleanup < 1

    def test_maybe_cleanup_runs_when_interval_elapsed(self):
        store = RateLimitStore()
        store._last_cleanup = time.time() - store.CLEANUP_INTERVAL - 10
        old = time.time() - store.CLEANUP_WINDOW - 100
        store._requests["old_key"] = [old]
        with patch.object(store, "cleanup_expired", wraps=store.cleanup_expired) as mock_cleanup:
            store._maybe_cleanup()
            mock_cleanup.assert_called_once()
        assert "old_key" not in store._requests

    def test_maybe_cleanup_skips_when_recent(self):
        store = RateLimitStore()
        store._last_cleanup = time.time()
        with patch.object(store, "cleanup_expired") as mock_cleanup:
            store._maybe_cleanup()
            mock_cleanup.assert_not_called()

    def test_clear_specific_and_all_keys(self):
        store = RateLimitStore()
        store._requests["a"] = [time.time()]
        store._requests["b"] = [time.time()]
        store.clear("a")
        assert "a" not in store._requests
        store.clear()
        assert store._requests == {}

    def test_is_allowed_blocks_with_retry_after(self):
        store = RateLimitStore()
        now = time.time()
        store._requests["key"] = [now - 5, now - 4, now - 3]  # 3 entries, max 3
        allowed, headers = store.is_allowed("key", 3, 60)
        assert allowed is False
        assert "Retry-After" in headers
        assert headers["X-RateLimit-Remaining"] == "0"

    def test_is_allowed_records_and_returns_remaining(self):
        store = RateLimitStore()
        allowed, headers = store.is_allowed("fresh", 5, 60)
        assert allowed is True
        assert headers["X-RateLimit-Remaining"] == "4"


class TestRateLimitMiddleware:
    def test_exempt_paths_default(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        assert "/health" in middleware.exempt_paths
        assert "/openapi.json" in middleware.exempt_paths

    @pytest.mark.asyncio
    async def test_exempt_path_bypasses(self):
        app = MagicMock()
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))
        middleware = RateLimitMiddleware(app=app)

        request = MagicMock(spec=Request)
        request.url.path = "/health"

        with patch(
            "cybershield.middleware.rate_limit.rate_limit_store",
            rate_limit_store,
        ):
            rate_limit_store.clear()
            response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_key_uses_api_key_limit_and_headers(self):
        app = MagicMock()
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))
        middleware = RateLimitMiddleware(app=app, api_key_limit=2)
        rate_limit_store.clear()

        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/jobs/"
        request.headers.get.return_value = "secret-key"  # X-API-Key present
        request.client = MagicMock()
        request.client.host = "1.2.3.4"

        with patch(
            "cybershield.middleware.rate_limit.rate_limit_store",
            rate_limit_store,
        ):
            # First two requests allowed
            await middleware.dispatch(request, call_next)
            await middleware.dispatch(request, call_next)
            # Third blocked
            blocked = await middleware.dispatch(request, call_next)
        assert blocked.status_code == 429
        assert blocked.headers["X-RateLimit-Limit"] == "2"

    @pytest.mark.asyncio
    async def test_ip_key_uses_client_host(self):
        app = MagicMock()
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))
        middleware = RateLimitMiddleware(app=app, default_limit=1)
        rate_limit_store.clear()

        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/jobs/"
        request.headers.get.return_value = None  # no API key
        request.client = MagicMock()
        request.client.host = "9.9.9.9"

        with patch(
            "cybershield.middleware.rate_limit.rate_limit_store",
            rate_limit_store,
        ):
            first = await middleware.dispatch(request, call_next)
            second = await middleware.dispatch(request, call_next)
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_response_gets_rate_limit_headers(self):
        app = MagicMock()
        response = JSONResponse({"ok": True})
        call_next = AsyncMock(return_value=response)
        middleware = RateLimitMiddleware(app=app, default_limit=10)
        rate_limit_store.clear()

        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/jobs/"
        request.headers.get.return_value = None
        request.client = MagicMock()
        request.client.host = "5.5.5.5"

        with patch(
            "cybershield.middleware.rate_limit.rate_limit_store",
            rate_limit_store,
        ):
            response = await middleware.dispatch(request, call_next)
        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Remaining"] == "9"
