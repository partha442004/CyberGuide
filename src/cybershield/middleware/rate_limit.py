"""
Rate Limiting Middleware

Provides configurable rate limiting using an in-memory sliding window algorithm.
Supports per-IP and per-API-key rate limiting with configurable limits.
"""

import logging
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitStore:
    """In-memory sliding window rate limit store with automatic cleanup."""

    CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes
    CLEANUP_WINDOW = 3600   # Remove entries older than 1 hour

    def __init__(self):
        self._requests: Dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if a request is allowed under the rate limit.

        Returns:
            Tuple of (allowed, headers) where headers contain rate limit info
        """
        # Run periodic cleanup for all keys
        self._maybe_cleanup()

        now = time.time()
        cutoff = now - window_seconds

        # Clean old entries for this key
        self._requests[key] = [
            t for t in self._requests[key] if t > cutoff
        ]

        current_count = len(self._requests[key])

        if current_count >= max_requests:
            retry_after = int(self._requests[key][0] + window_seconds - now) + 1
            headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(cutoff + window_seconds)),
                "Retry-After": str(retry_after),
            }
            return False, headers

        # Record this request
        self._requests[key].append(now)
        new_count = current_count + 1
        remaining = max(0, max_requests - new_count)

        headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(cutoff + window_seconds)),
        }
        return True, headers

    def cleanup_expired(self):
        """Remove entries older than CLEANUP_WINDOW for all keys."""
        now = time.time()
        cutoff = now - self.CLEANUP_WINDOW
        keys_to_remove = []
        for key, timestamps in self._requests.items():
            self._requests[key] = [t for t in timestamps if t > cutoff]
            if not self._requests[key]:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._requests[key]
        self._last_cleanup = now
        return len(keys_to_remove)

    def _maybe_cleanup(self):
        """Run periodic cleanup if interval has elapsed."""
        now = time.time()
        if now - self._last_cleanup > self.CLEANUP_INTERVAL:
            removed = self.cleanup_expired()
            if removed:
                logger.debug(f"Rate limit cleanup: removed {removed} expired keys")

    def clear(self, key: Optional[str] = None):
        """Clear rate limit data for a key or all keys."""
        if key:
            self._requests.pop(key, None)
        else:
            self._requests.clear()


# Global rate limit store
rate_limit_store = RateLimitStore()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.

    Limits:
    - Per IP: 100 requests per minute (default)
    - Per API key: 1000 requests per minute (default)
    - Health/docs endpoints: Exempt from rate limiting
    """

    def __init__(
        self,
        app,
        default_limit: int = 100,
        default_window: int = 60,
        api_key_limit: int = 1000,
        exempt_paths: Optional[list[str]] = None,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.api_key_limit = api_key_limit
        self.exempt_paths = exempt_paths or [
            "/health",
            "/api/docs",
            "/api/redoc",
            "/openapi.json",
            "/",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter."""
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Determine rate limit key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            key = f"apikey:{api_key}"
            limit = self.api_key_limit
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip:{client_ip}"
            limit = self.default_limit

        # Check rate limit
        allowed, headers = rate_limit_store.is_allowed(
            key, limit, self.default_window
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for {key}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RATE_LIMITED",
                    "message": "Too many requests. Please try again later.",
                },
                headers=headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header, value in headers.items():
            response.headers[header] = value

        return response
