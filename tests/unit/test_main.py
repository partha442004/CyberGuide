"""
Unit tests for the FastAPI app entry point: exception handlers, CORS config,
and security validation.
"""

import json

import pytest
from starlette.requests import Request

from interntrack.config import Settings
from interntrack.domain.exceptions import AppException, NotFoundError
from interntrack.main import domain_exception_handler, global_exception_handler


def _make_request() -> Request:
    """Build a minimal ASGI Request for handler tests."""
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
    )


class TestDomainExceptionHandler:
    """Tests for the AppException -> HTTP response handler."""

    @pytest.mark.asyncio
    async def test_returns_status_and_payload(self):
        """Domain exceptions surface their status code and error payload."""
        exc = NotFoundError(resource="Job", identifier="abc-123")
        response = await domain_exception_handler(_make_request(), exc)

        assert response.status_code == 404
        data = json.loads(response.body)
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Job with identifier 'abc-123' not found"
        assert data["error"]["details"] == {"resource": "Job", "identifier": "abc-123"}

    @pytest.mark.asyncio
    async def test_base_app_exception_defaults(self):
        """Base AppException defaults to 500 with a generic code."""
        exc = AppException("something broke")
        response = await domain_exception_handler(_make_request(), exc)

        assert response.status_code == 500
        data = json.loads(response.body)
        assert data["error"]["code"] == "APP_ERROR"
        assert data["error"]["message"] == "something broke"


class TestGlobalExceptionHandler:
    """Tests for the global fallback exception handler."""

    @pytest.mark.asyncio
    async def test_returns_500_with_consistent_shape(self):
        """Unhandled exceptions become 500 with a consistent error shape."""
        response = await global_exception_handler(_make_request(), RuntimeError("boom"))

        assert response.status_code == 500
        data = json.loads(response.body)
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert data["error"]["message"] == "An error occurred"
        assert isinstance(data["error"]["details"], dict)


class TestCorsConfig:
    """Tests for CORS settings parsing."""

    def test_cors_origins_csv_parsing(self):
        """Comma-separated CORS_ORIGINS env values are split and stripped."""
        settings = Settings(cors_origins="https://a.example.com, https://b.example.com")
        assert settings.cors_origins == [
            "https://a.example.com",
            "https://b.example.com",
        ]

    def test_cors_origins_list_passthrough(self):
        """Programmatic list values are preserved as-is."""
        settings = Settings(cors_origins=["https://a.example.com"])
        assert settings.cors_origins == ["https://a.example.com"]

    def test_cors_empty_string_yields_empty_list(self):
        """An empty CORS_ORIGINS value yields no origins."""
        settings = Settings(cors_origins="")
        assert settings.cors_origins == []


class TestValidateSecurity:
    """Tests for the security configuration validator."""

    def test_warns_on_default_secret_and_open_cors(self):
        """The dev-default secret key and wildcard CORS produce warnings."""
        settings = Settings(
            secret_key="change-me-in-production",  # noqa: S106
            cors_allow_all=True,
            cors_origins=["*"],
        )
        warnings = settings.validate_security()

        assert any("SECRET_KEY" in warning for warning in warnings)
        assert any("CORS" in warning for warning in warnings)

    def test_clean_when_hardened(self):
        """A strong secret and restricted CORS produce no warnings."""
        settings = Settings(
            secret_key="super-secret-value",  # noqa: S106
            cors_allow_all=False,
            cors_origins=["https://app.example.com"],
        )
        assert settings.validate_security() == []

    def test_is_production_reflects_debug(self):
        """is_production is the inverse of debug."""
        assert Settings(debug=False).is_production is True
        assert Settings(debug=True).is_production is False
