"""Tests for the X-Cron-Secret guard on scheduled-maintenance endpoints."""

import pytest
from fastapi import HTTPException

from interntrack.api.deps import require_cron_secret


class _FakeSettings:
    def __init__(self, cron_secret: str | None):
        self.cron_secret = cron_secret


@pytest.mark.asyncio
async def test_guard_is_noop_when_secret_unset(monkeypatch):
    """Default deployments (no CRON_SECRET) keep the endpoints open."""
    monkeypatch.setattr(
        "interntrack.api.deps.get_settings", lambda: _FakeSettings(None)
    )
    await require_cron_secret(x_cron_secret=None)
    await require_cron_secret(x_cron_secret="test-open")  # noqa: S106


@pytest.mark.asyncio
async def test_guard_accepts_matching_header(monkeypatch):
    monkeypatch.setattr(
        "interntrack.api.deps.get_settings", lambda: _FakeSettings("test-secret-ok")
    )
    await require_cron_secret(x_cron_secret="test-secret-ok")  # noqa: S106  # noqa: S106


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, "", "wrong-value"])
async def test_guard_rejects_missing_or_wrong_header(monkeypatch, header):
    monkeypatch.setattr(
        "interntrack.api.deps.get_settings", lambda: _FakeSettings("s3cret")
    )
    with pytest.raises(HTTPException) as exc:
        await require_cron_secret(x_cron_secret=header)
    assert exc.value.status_code == 401
