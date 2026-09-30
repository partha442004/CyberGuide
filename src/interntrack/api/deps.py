"""Shared FastAPI dependencies."""

import secrets

from fastapi import Header, HTTPException

from interntrack.config import get_settings


async def require_cron_secret(
    x_cron_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Guard for the scheduled-maintenance (cron-triggered) endpoints.

    When ``CRON_SECRET`` is configured, requests must carry a matching
    ``X-Cron-Secret`` header — or Vercel Cron's automatic
    ``Authorization: Bearer <CRON_SECRET>`` — or they are rejected with
    401. The Bearer form exists because Vercel Cron cannot attach custom
    headers: it always sends the standard Authorization header, so the
    digest endpoints can be fired on-time by Vercel instead of GitHub's
    irregular scheduler. When the setting is unset, the guard is a no-op
    so local development and pre-secret deployments behave exactly as
    before (the Telegram webhook keeps its own dedicated secret).
    """
    settings = get_settings()
    expected = settings.cron_secret
    if not expected:
        return
    if x_cron_secret and secrets.compare_digest(x_cron_secret, expected):
        return
    # FastAPI injects this as str | None; direct (non-DI) callers may leave
    # the raw Header marker object — only treat genuine strings as a header.
    if isinstance(authorization, str) and authorization:
        scheme, _, credential = authorization.partition(" ")
        if (
            scheme.lower() == "bearer"
            and credential
            and secrets.compare_digest(credential.strip(), expected)
        ):
            return
    raise HTTPException(
        status_code=401,
        detail="Missing or invalid X-Cron-Secret header",
    )
