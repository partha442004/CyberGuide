"""
Unit Tests for the FastAPI application entry point (extended)

Covers the remaining lines of ``cybershield/main.py``:
- The ``lifespan`` startup/shutdown sequence
- Conditional APIKeyMiddleware registration at import time
- Both exception handlers
"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from starlette.responses import JSONResponse

import cybershield.main as main_module
from cybershield.config import get_settings
from cybershield.domain.exceptions import CyberGuideException
from cybershield.main import (
    app,
    cybershield_exception_handler,
    global_exception_handler,
    lifespan,
)
from cybershield.middleware import APIKeyMiddleware


class TestLifespan:
    """Tests for the application lifespan manager."""

    @pytest.mark.asyncio
    async def test_startup_and_shutdown_sequence(self):
        """Should init DB + Elasticsearch on startup and close on shutdown."""
        with (
            patch("cybershield.main.init_db", new=AsyncMock()) as mock_init,
            patch("cybershield.main.es.init_elasticsearch", new=AsyncMock()) as mock_es_init,
            patch("cybershield.main.es.close_elasticsearch", new=AsyncMock()) as mock_es_close,
        ):
            async with lifespan(app):
                mock_init.assert_awaited_once()
                mock_es_init.assert_awaited_once()
                mock_es_close.assert_not_awaited()

        mock_es_close.assert_awaited_once()


class TestAPIKeyMiddlewareRegistration:
    """Tests for the import-time conditional middleware registration."""

    def test_api_key_middleware_added_when_configured(self, monkeypatch):
        """When require_api_key + api_keys are set, APIKeyMiddleware is added."""
        monkeypatch.setenv("REQUIRE_API_KEY", "true")
        monkeypatch.setenv("API_KEYS", "test-key-123")
        get_settings.cache_clear()
        importlib.reload(main_module)

        reloaded_app = main_module.app
        middleware_classes = [m.cls for m in reloaded_app.user_middleware]
        assert APIKeyMiddleware in middleware_classes

        # Restore default settings and app for the rest of the test session.
        monkeypatch.delenv("REQUIRE_API_KEY", raising=False)
        monkeypatch.delenv("API_KEYS", raising=False)
        get_settings.cache_clear()
        importlib.reload(main_module)


class TestExceptionHandlers:
    """Tests for the CyberGuide and global exception handlers."""

    @pytest.mark.asyncio
    async def test_cybershield_exception_handler_returns_json(self):
        """Should render CyberGuideException into a JSON response."""
        exc = CyberGuideException(
            message="Something went wrong",
            code="TEST_ERROR",
            status=422,
            details={"field": "value"},
        )
        request = MagicMock(spec=Request)
        response = await cybershield_exception_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        body = bytes(response.body).decode()
        assert '"error":"TEST_ERROR"' in body
        assert '"message":"Something went wrong"' in body
        assert '"details"' in body

    @pytest.mark.asyncio
    async def test_global_exception_handler_returns_500(self):
        """Should render unexpected exceptions into a 500 JSON response."""
        request = MagicMock(spec=Request)
        response = await global_exception_handler(request, RuntimeError("boom"))

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        body = bytes(response.body).decode()
        assert '"error":"INTERNAL_ERROR"' in body
        assert '"message":"An unexpected error occurred"' in body
