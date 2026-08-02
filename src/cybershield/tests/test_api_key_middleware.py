"""
Tests for the API Key authentication middleware.

Exercises exempt paths, missing/invalid/valid API keys, open (no-keys) mode,
and a custom header name — using a minimal Starlette app with the middleware
injected directly.

Note: ``APIKeyMiddleware.__init__`` calls ``get_settings()`` when the
middleware stack is built (on the first request), so an autouse fixture keeps
``get_settings`` patched for the entire test to make open-mode behavior
deterministic (independent of ambient ``API_KEYS`` env vars).
"""

from typing import Any, Optional, Set, cast
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from cybershield.middleware.auth import APIKeyMiddleware


@pytest.fixture(autouse=True)
def _no_api_keys_in_settings():
    """Force get_settings() to report no configured API keys for all tests."""
    settings_mock = type("Settings", (), {"api_keys": None})()
    with patch("cybershield.middleware.auth.get_settings", return_value=settings_mock):
        yield


def _make_app(api_keys: Optional[Set[str]] = None, header: str = "X-API-Key"):
    """Build a minimal Starlette app protected by APIKeyMiddleware."""

    async def protected(request):
        # Echo back the api_key stored on request.state for verification.
        return JSONResponse({"ok": True, "api_key": getattr(request.state, "api_key", None)})

    app = Starlette(routes=[Route("/protected", protected), Route("/health", protected)])
    app.add_middleware(
        APIKeyMiddleware,
        api_keys=api_keys,
        api_key_header=header,
        exempt_paths={"/health"},
    )
    return app


def _client_for(app):
    transport = ASGITransport(app=cast(Any, app))
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_exempt_path_skips_authentication():
    """Public endpoints pass without an API key."""
    app = _make_app(api_keys={"secret123"})
    async with _client_for(app) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["ok"] is True


@pytest.mark.asyncio
async def test_missing_api_key_returns_401():
    """No API key header on a protected path -> 401 MISSING_API_KEY."""
    app = _make_app(api_keys={"secret123"})
    async with _client_for(app) as client:
        response = await client.get("/protected")
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "MISSING_API_KEY"
        assert "X-API-Key" in body["message"]


@pytest.mark.asyncio
async def test_invalid_api_key_returns_403():
    """A wrong API key on a protected path -> 403 INVALID_API_KEY."""
    app = _make_app(api_keys={"secret123"})
    async with _client_for(app) as client:
        response = await client.get("/protected", headers={"X-API-Key": "wrong"})
        assert response.status_code == 403
        assert response.json()["error"] == "INVALID_API_KEY"


@pytest.mark.asyncio
async def test_valid_api_key_passes_and_sets_state():
    """A correct API key -> 200 and request.state.api_key is set."""
    app = _make_app(api_keys={"secret123"})
    async with _client_for(app) as client:
        response = await client.get("/protected", headers={"X-API-Key": "secret123"})
        assert response.status_code == 200
        assert response.json()["api_key"] == "secret123"


@pytest.mark.asyncio
async def test_custom_header_name():
    """A custom header name is honored by the middleware."""
    app = _make_app(api_keys={"secret123"}, header="X-Auth-Token")
    async with _client_for(app) as client:
        # Wrong default header -> 401
        resp_default = await client.get("/protected", headers={"X-API-Key": "secret123"})
        assert resp_default.status_code == 401
        # Correct custom header -> 200
        resp_custom = await client.get("/protected", headers={"X-Auth-Token": "secret123"})
        assert resp_custom.status_code == 200


@pytest.mark.asyncio
async def test_no_api_keys_open_mode_allows_all():
    """With no keys configured, protected paths pass without a key."""
    app = _make_app(api_keys=None)
    async with _client_for(app) as client:
        response = await client.get("/protected")
        assert response.status_code == 200
        assert response.json()["ok"] is True


@pytest.mark.asyncio
async def test_missing_key_logs_and_returns_401_when_keys_configured():
    """Regression: configured keys still enforce auth on protected paths."""
    app = _make_app(api_keys={"a", "b"})
    async with _client_for(app) as client:
        response = await client.get("/protected")
        assert response.status_code == 401
