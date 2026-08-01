"""
Rate Limiting Middleware

Provides configurable rate limiting using a sliding window algorithm. Supports
per-IP and per-API-key rate limiting with configurable limits.

Two store implementations back the middleware:

- :class:`RateLimitStore` — dependency-free in-memory sliding window (the
  default; per-process limits).
- :class:`RedisRateLimitStore` — Redis-backed sliding window using an atomic
  Lua script (ZSET), so limits are shared across API replicas. Falls back to
  the in-memory store when Redis is unreachable so the API never fails closed.

Responses use the standard InternTrack error contract::

    {"error": {"code": "RATE_LIMITED", "message": "...", "details": {}}}
"""

import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitStore:
    """In-memory sliding window rate limit store with automatic cleanup."""

    CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes
    CLEANUP_WINDOW = 3600  # Remove entries older than 1 hour

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict[str, str]]:
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
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

        current_count = len(self._requests[key])

        if current_count >= max_requests:
            retry_after = int(self._requests[key][0] + window_seconds - now) + 1
            headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + window_seconds)),
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
            "X-RateLimit-Reset": str(int(now + window_seconds)),
        }
        return True, headers

    async def is_allowed_async(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict[str, str]]:
        """Async alias of :meth:`is_allowed` (shared middleware code path)."""
        return self.is_allowed(key, max_requests, window_seconds)

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
                logger.debug("Rate limit cleanup: removed %s expired keys", removed)

    def clear(self, key: str | None = None):
        """Clear rate limit data for a key or all keys."""
        if key:
            self._requests.pop(key, None)
        else:
            self._requests.clear()


# Global in-memory rate limit store (used when Redis is not configured)
rate_limit_store = RateLimitStore()


class RedisRateLimitStore:
    """
    Redis-backed sliding window rate limit store (multi-instance safe).

    Uses a sorted set per key plus an atomic Lua script so the prune, count
    and record happen in one round trip with no TOCTOU races. Falls back to
    an in-memory :class:`RateLimitStore` when Redis is unreachable so the API
    keeps serving with per-instance limits during an outage.
    """

    # Lua sliding window: KEYS[1] is the key; ARGV holds now, window, max.
    _SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= max_requests then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry_after = 0
  if oldest[2] then
    retry_after = math.floor(tonumber(oldest[2]) + window - now) + 1
  end
  return {0, retry_after}
end
local member = now .. ':' .. redis.call('INCR', key .. ':seq')
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window)
-- Keep the seq counter in lockstep with the zset so it never leaks and
-- never resets while the zset is alive (avoids same-second member collisions).
redis.call('EXPIRE', key .. ':seq', window)
local remaining = max_requests - count - 1
return {1, remaining}
"""

    def __init__(self, redis_url: str, connect_timeout: float = 2.0):

        self._redis_url = redis_url
        self._connect_timeout = connect_timeout
        self._client: Any = None
        self._fallback = RateLimitStore()
        self._degraded = False

    async def _get_client(self):
        """Lazily create the Redis client (avoids failing at import time)."""
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(
                self._redis_url,
                socket_connect_timeout=self._connect_timeout,
                socket_timeout=self._connect_timeout,
            )
        return self._client

    async def is_allowed_async(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict[str, str]]:
        """Check a request against the Redis-backed sliding window."""
        try:
            client = await self._get_client()
            now = time.time()
            result = await client.eval(
                self._SLIDING_WINDOW_LUA,
                1,
                f"rl:{key}",
                now,
                window_seconds,
                max_requests,
            )
            allowed = bool(result[0])
            value = int(result[1])
            if not allowed:
                headers = {
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + window_seconds)),
                    "Retry-After": str(max(1, value)),
                }
                return False, headers
            headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(max(0, value)),
                "X-RateLimit-Reset": str(int(now + window_seconds)),
            }
            return True, headers
        except Exception:
            # Redis unreachable: degrade to the in-memory store so the API
            # keeps serving (per-instance limits until Redis returns).
            if not self._degraded:
                self._degraded = True
                logger.warning(
                    "Redis rate limit store unreachable; falling back to "
                    "in-memory store",
                )
            return self._fallback.is_allowed(key, max_requests, window_seconds)

    async def cleanup_expired(self):
        """Redis keys self-expire (EXPIRE); nothing to sweep here."""
        return 0

    async def clear(self, key: str | None = None):
        """Clear rate limit data for a key or all keys in Redis."""
        try:
            client = await self._get_client()
            if key:
                await client.delete(f"rl:{key}")
                await client.delete(f"rl:{key}:seq")
            else:
                # Scan and delete all rate-limit keys
                async for redis_key in client.scan_iter("rl:*"):
                    await client.delete(redis_key)
        except Exception:
            self._fallback.clear(key)


def get_rate_limit_store():
    """
    Build the configured rate limit store.

    Returns a :class:`RedisRateLimitStore` when ``REDIS_URL`` is configured
    (multi-instance shared limits) and the global in-memory store otherwise.
    """
    from interntrack.config import get_settings

    settings = get_settings()
    if settings.redis_url:
        try:
            return RedisRateLimitStore(settings.redis_url)
        except Exception:
            logger.warning(
                "Redis rate limit store init failed; using in-memory store",
            )
    return rate_limit_store


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.

    Limits:
    - Per IP: 100 requests per minute (default)
    - Per API key: 1000 requests per minute (default)
    - Health/docs/root/metrics endpoints: Exempt from rate limiting
    """

    def __init__(
        self,
        app,
        default_limit: int = 100,
        default_window: int = 60,
        api_key_limit: int = 1000,
        api_key_header: str = "X-API-Key",
        exempt_paths: list[str] | None = None,
        store=None,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.api_key_limit = api_key_limit
        self.api_key_header = api_key_header
        self.store = store or rate_limit_store
        self.exempt_paths = exempt_paths or [
            "/",
            "/health",
            "/metrics",
            "/metrics/prometheus",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter."""
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Determine rate limit key
        api_key = request.headers.get(self.api_key_header)
        if api_key:
            key = f"apikey:{api_key}"
            limit = self.api_key_limit
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip:{client_ip}"
            limit = self.default_limit

        # Check rate limit
        allowed, headers = await self.store.is_allowed_async(
            key,
            limit,
            self.default_window,
        )

        if not allowed:
            logger.warning("Rate limit exceeded for %s", key)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again later.",
                        "details": {},
                    },
                },
                headers=headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header, value in headers.items():
            response.headers[header] = value

        return response
