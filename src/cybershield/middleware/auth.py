"""
API Key Authentication Middleware

Provides API key validation for securing API endpoints.
Supports multiple API keys and optional bypass for public endpoints.
"""

import logging
from typing import Optional, Set

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cybershield.config import get_settings

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API Key authentication middleware for FastAPI.

    Validates API keys from the X-API-Key header against configured keys.
    Exempts public endpoints (health, docs, etc.) from authentication.
    """

    def __init__(
        self,
        app,
        api_key_header: str = "X-API-Key",
        exempt_paths: Optional[Set[str]] = None,
        api_keys: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.api_key_header = api_key_header
        self.exempt_paths = exempt_paths or {
            "/",
            "/health",
            "/api/docs",
            "/api/redoc",
            "/openapi.json",
        }
        # Load API keys from settings or use provided set
        settings = get_settings()
        if api_keys:
            self.api_keys = api_keys
        elif hasattr(settings, "api_keys") and settings.api_keys:
            self.api_keys = set(settings.api_keys)
        else:
            # If no API keys configured, allow all requests (development mode)
            self.api_keys = set()
            logger.warning(
                "No API keys configured - running in open mode. "
                "Set API_KEYS environment variable for production."
            )

    async def dispatch(self, request: Request, call_next):
        """Process request through API key validator."""
        # Skip validation for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # If no API keys are configured, allow all requests
        if not self.api_keys:
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get(self.api_key_header)

        if not api_key:
            logger.warning(
                f"Missing API key from {request.client.host if request.client else 'unknown'}"
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "MISSING_API_KEY",
                    "message": f"API key required in {self.api_key_header} header",
                },
            )

        # Validate API key
        if api_key not in self.api_keys:
            logger.warning(
                f"Invalid API key attempt from {request.client.host if request.client else 'unknown'}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "INVALID_API_KEY",
                    "message": "Invalid API key",
                },
            )

        # Add API key info to request state for downstream use
        request.state.api_key = api_key

        return await call_next(request)
