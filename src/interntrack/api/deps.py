"""Shared FastAPI dependencies."""

import secrets

from fastapi import Header, HTTPException

from interntrack.config import get_settings


async def require_cron_secret(
    x_cron_secret: str | None = Header(default=None),
) -> None:
    """Guard for the scheduled-maintenance (cron-triggered) endpoints.

    When ``CRON_SECRET`` is configured, requests must carry a matching
    ``X-Cron-Secret`` header or they are rejected with 401 — this stops
    strangers from triggering discovery runs, digest sends or archives
    against the public deployment. When the setting is unset, the guard is
    a no-op so local development and pre-secret deployments behave exactly
    as before (the Telegram webhook keeps its own dedicated secret).
    """
    settings = get_settings()
    expected = settings.cron_secret
    if not expected:
        return
    if not x_cron_secret or not secrets.compare_digest(x_cron_secret, expected):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-Cron-Secret header",
        )
