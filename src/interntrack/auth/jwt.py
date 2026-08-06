"""
JWT authentication helpers for InternTrack.

Provides token creation, verification, and dependency injection
for FastAPI endpoints that require authentication.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from interntrack.config import get_settings

try:
    import jwt
except ImportError:
    # Fallback: minimal HMAC-SHA256 JWT using stdlib
    import base64
    import hashlib
    import json

    class _JWT:
        """Minimal JWT implementation using stdlib only."""

        @staticmethod
        def encode(payload: dict, key: str, algorithm: str = "HS256") -> str:
            header = (
                base64.urlsafe_b64encode(
                    json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
                )
                .rstrip(b"=")
                .decode()
            )
            body = (
                base64.urlsafe_b64encode(json.dumps(payload).encode())
                .rstrip(b"=")
                .decode()
            )
            sig_input = f"{header}.{body}".encode()
            sig = (
                base64.urlsafe_b64encode(
                    hmac.new(key.encode(), sig_input, hashlib.sha256).digest()
                )
                .rstrip(b"=")
                .decode()
            )
            return f"{header}.{body}.{sig}"

        @staticmethod
        def decode(token: str, key: str, algorithms: list | None = None) -> dict:
            import hmac

            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid token")
            header, body, sig = parts
            sig_input = f"{header}.{body}".encode()
            expected = (
                base64.urlsafe_b64encode(
                    hmac.new(key.encode(), sig_input, hashlib.sha256).digest()
                )
                .rstrip(b"=")
                .decode()
            )
            if not hmac.compare_digest(sig, expected):
                raise ValueError("Invalid signature")
            padding = 4 - len(body) % 4
            body_padded = body + "=" * padding
            return json.loads(base64.urlsafe_b64decode(body_padded))

    import hmac

    jwt = _JWT()  # type: ignore[assignment]

# Re-export for type checking
try:
    import jwt as _jwt_module

    _HAS_PYJWT = True
except ImportError:
    _HAS_PYJWT = False

_bearer = HTTPBearer(auto_error=False)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    if _HAS_PYJWT:
        return _jwt_module.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    return jwt.encode(  # type: ignore[union-attr]
        to_encode,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a JWT refresh token with longer expiry."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(
        days=settings.jwt_refresh_token_expire_days,
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    if _HAS_PYJWT:
        return _jwt_module.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    return jwt.encode(  # type: ignore[union-attr]
        to_encode,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    settings = get_settings()
    if _HAS_PYJWT:
        return _jwt_module.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    return jwt.decode(  # type: ignore[union-attr]
        token,
        settings.jwt_secret_key,
        [settings.jwt_algorithm],
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency: extract and verify the current user from the
    Authorization header.

    Returns the decoded token payload (contains ``sub`` = user_id).
    Raises 401 if the token is missing, expired or invalid.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user ID")
    return payload


async def optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """Like get_current_user but returns None when no token is present
    (for endpoints that work both with and without auth).
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# ─── Usage Tracking ─────────────────────────────────────────────────

import threading  # noqa: E402
from collections import defaultdict  # noqa: E402
from datetime import date  # noqa: E402

_lock = threading.Lock()
_daily_usage: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
_monthly_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def track_api_usage(user_id: str) -> bool:
    """Record an API call for the user. Returns False if quota exceeded."""
    settings = get_settings()
    today = date.today()
    month_key = today.strftime("%Y-%m")

    with _lock:
        # Daily
        _daily_usage[user_id][today] += 1
        daily_count = _daily_usage[user_id][today]
        if daily_count > settings.api_daily_quota:
            _daily_usage[user_id][today] -= 1
            return False

        # Monthly
        _monthly_usage[user_id][month_key] += 1
        monthly_count = _monthly_usage[user_id][month_key]
        if monthly_count > settings.api_monthly_quota:
            _monthly_usage[user_id][month_key] -= 1
            return False

    return True


def get_usage_stats(user_id: str) -> dict:
    """Get current usage stats for a user."""
    settings = get_settings()
    today = date.today()
    month_key = today.strftime("%Y-%m")

    with _lock:
        daily = _daily_usage[user_id][today]
        monthly = _monthly_usage[user_id][month_key]

    return {
        "daily": {
            "used": daily,
            "limit": settings.api_daily_quota,
            "remaining": max(0, settings.api_daily_quota - daily),
        },
        "monthly": {
            "used": monthly,
            "limit": settings.api_monthly_quota,
            "remaining": max(0, settings.api_monthly_quota - monthly),
        },
    }


# ─── Real-time Discovery Cache ──────────────────────────────────────

from datetime import datetime as _dt  # noqa: E402

_discovery_cache: dict[str, tuple[_dt, list[dict]]] = {}
_CACHE_TTL_SECONDS = 7200  # 2 hours


def get_cached_discovery(query: str, location: str | None = None) -> list[dict] | None:
    """Return cached discovery results if fresh enough."""
    key = f"{query}:{location or ''}"
    with _lock:
        if key in _discovery_cache:
            ts, results = _discovery_cache[key]
            if (_dt.utcnow() - ts).total_seconds() < _CACHE_TTL_SECONDS:
                return results
            del _discovery_cache[key]
    return None


def set_discovery_cache(query: str, location: str | None, results: list[dict]):
    """Store discovery results in cache."""
    key = f"{query}:{location or ''}"
    with _lock:
        _discovery_cache[key] = (_dt.utcnow(), results)
