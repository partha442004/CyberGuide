"""Tests for the watchdog alert endpoint and durable metrics.

``POST /v1/observability/watchdog-alert`` pages the owner's configured
channels when the 5-minute Actions health watchdog has seen two
consecutive failures; ``GET /metrics`` now carries a ``durable`` section
computed from the database that survives serverless instance resets and
degrades to ``{"status": "error"}`` when the DB is unreachable.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from interntrack.database.session import get_db
    from interntrack.main import app

    async def _noop_db():
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = _noop_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db, None)


def _fake_manager(results: dict[str, bool]):
    manager = SimpleNamespace(
        get_configured_channels=lambda: list(results.keys()),
        notify=None,
    )

    async def _notify(channels, message, subject=None, buttons=None, recipient=None):
        return {c: results.get(c, False) for c in channels}

    manager.notify = _notify
    return manager


def test_watchdog_alert_pages_all_configured_channels(client):
    from interntrack.database.session import get_db

    async def _supply():
        yield SimpleNamespace()

    client.app.dependency_overrides[get_db] = _supply

    manager = _fake_manager({"telegram": True, "email": False})
    with patch(
        "interntrack.services.notification_service.NotificationManager",
        return_value=manager,
    ):
        resp = client.post("/api/v1/observability/watchdog-alert")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True  # at least one channel delivered
    assert body["results"] == {"telegram": True, "email": False}


def test_watchdog_alert_reports_total_failure(client):
    from interntrack.database.session import get_db

    async def _supply():
        yield SimpleNamespace()

    client.app.dependency_overrides[get_db] = _supply

    manager = _fake_manager({"telegram": False})
    with patch(
        "interntrack.services.notification_service.NotificationManager",
        return_value=manager,
    ):
        resp = client.post("/api/v1/observability/watchdog-alert")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_metrics_durable_section_present(client, monkeypatch):
    """/metrics carries the DB-backed durable section alongside memory."""

    async def _fake_durable():
        return {"jobs_total": 42, "members_total": 13}

    monkeypatch.setattr("interntrack.main._durable_metrics", _fake_durable)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["durable"]["jobs_total"] == 42
    assert body["durable"]["members_total"] == 13


def test_metrics_durable_degrades_on_db_error(client, monkeypatch):
    """DB down → durable section says error; endpoint still answers 200."""

    async def _boom():
        raise RuntimeError("db gone")

    monkeypatch.setattr("interntrack.main._durable_metrics", _boom)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.json()["durable"] == {"status": "error"}
