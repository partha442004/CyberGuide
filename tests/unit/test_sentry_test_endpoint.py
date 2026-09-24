"""Tests for the guarded Sentry delivery-test endpoint.

``GET /v1/observability/debug/sentry-test`` exists to prove the deployed
error pipeline end-to-end: with ``SENTRY_DSN`` configured it raises an
unhandled ``RuntimeError`` that the Sentry FastAPI integration captures;
without it the endpoint is inert and answers ``skipped`` instead of
generating 500 noise. Both paths are covered here, plus the cron-secret
gate inherited from the observability router.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from interntrack.database.session import get_db
    from interntrack.main import app

    # The endpoint never touches the database; the override keeps the
    # dependency wiring honest without needing a SQLite fixture.
    async def _noop_db():
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = _noop_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db, None)


def test_sentry_test_skips_without_sentry(client):
    """Without SENTRY_DSN the endpoint is inert instead of a noise source."""
    resp = client.get("/api/v1/observability/debug/sentry-test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "skipped"
    assert "SENTRY_DSN" in body["reason"]


def test_sentry_test_raises_when_sentry_initialized(client):
    """With Sentry initialized the endpoint deliberately blows up (captured)."""
    fake_client = SimpleNamespace(dsn="https://example.ingest.sentry.io/1")
    with patch("sentry_sdk.get_client", return_value=fake_client):
        resp = client.get("/api/v1/observability/debug/sentry-test")
    assert resp.status_code == 500


def test_sentry_test_skips_when_dsn_unset(client):
    """SDK 2.x init(dsn=None) yields an active-but-inert client: no probe hit."""
    fake_client = SimpleNamespace(dsn=None)
    with patch("sentry_sdk.get_client", return_value=fake_client):
        resp = client.get("/api/v1/observability/debug/sentry-test")
    assert resp.status_code == 200


def test_sentry_test_requires_cron_secret(client, monkeypatch):
    """The route inherits the observability router's cron-secret guard."""
    from interntrack.api import deps as deps_module

    monkeypatch.setattr(
        deps_module,
        "get_settings",
        lambda: SimpleNamespace(cron_secret="s3cret"),  # noqa: S106
    )
    resp = client.get("/api/v1/observability/debug/sentry-test")
    assert resp.status_code == 401
