"""Tests for the cron-guarded reliability digest endpoint.

``POST /v1/observability/reliability-digest`` flips the owner's alert
preferences to fresher-only (idempotently), aggregates 7-day discovery
and delivery stats, and — when configured — pulls UptimeRobot uptime and
self-checks the Telegram channel. The endpoint must never fail wholesale:
each optional section degrades to a ``skipped``/``error`` marker.
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


def _fake_db(no_owner: bool = False):
    owner = SimpleNamespace(
        id="owner-1",
        email="owner@example.com",
        access_token="tok-1",  # noqa: S106
    )
    pref = SimpleNamespace(
        user_id="owner-1", domains=["grc"], experience_levels=[], is_enabled=True
    )

    class _Scalars:
        def __init__(self, rows):
            self._rows = rows

        def first(self):
            return self._rows[0] if self._rows else None

        def all(self):
            return self._rows

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return _Scalars(self._rows)

        def all(self):
            return self._rows

    class _DB:
        def __init__(self):
            self.added: list = []

        async def execute(self, stmt):
            desc = str(getattr(stmt, "column_descriptions", "") or "")
            if "AlertPreferences" in desc:
                return _Result([] if no_owner else [pref])
            if "User" in desc:
                return _Result([] if no_owner else [owner])
            return _Result([])

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            return None

    return _DB()


def _wire_db(client, db):
    from interntrack.database.session import get_db

    async def _supply():
        yield db

    app_ref = client.app
    app_ref.dependency_overrides[get_db] = _supply


def test_digest_reports_skipped_uptime_without_key(client, monkeypatch):
    """No UPTIMEROBOT_API_KEY → the uptime section says skipped, not 500."""
    from interntrack.config import get_settings

    monkeypatch.setattr(
        type(get_settings()),
        "uptimerobot_api_key",
        property(lambda _self: None),  # noqa: ARG005
        raising=False,
    )
    db = _fake_db(no_owner=True)

    async def _supply():
        yield db

    from interntrack.database.session import get_db

    client.app.dependency_overrides[get_db] = _supply

    resp = client.post("/api/v1/observability/reliability-digest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["uptime"]["status"] == "skipped"
    assert body["owner_prefs"]["owner_found"] is False
    assert body["discovery_7d"] == {}
    assert body["delivery_7d"] == {}


def test_digest_applies_fresher_only_prefs(client, monkeypatch):
    """Owner found → domains and experience levels are flipped, idempotently."""
    from interntrack.config import get_settings

    monkeypatch.setattr(
        type(get_settings()),
        "uptimerobot_api_key",
        property(lambda _self: None),  # noqa: ARG005
        raising=False,
    )
    db = _fake_db()

    async def _supply():
        yield db

    from interntrack.database.session import get_db

    client.app.dependency_overrides[get_db] = _supply

    resp = client.post("/api/v1/observability/reliability-digest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner_prefs"]["owner_found"] is True
    assert body["owner_prefs"]["domains"] == ["security", "cloud"]
    assert body["owner_prefs"]["experience_levels"] == ["fresher", "intern"]


def test_digest_pulls_uptime_when_key_present(client, monkeypatch):
    """With an API key the uptime section reports per-monitor 7-day ratios."""
    from interntrack.config import get_settings

    monkeypatch.setattr(
        type(get_settings()),
        "uptimerobot_api_key",
        property(lambda _self: "u123-test"),  # noqa: ARG005
        raising=False,
    )
    db = _fake_db(no_owner=True)

    async def _supply():
        yield db

    from interntrack.database.session import get_db

    client.app.dependency_overrides[get_db] = _supply

    payload = {
        "monitors": [
            {
                "friendly_name": "cyberguide-api",
                "custom_uptime_ratio": "100.000",
                "status": 2,
            }
        ]
    }

    class _Resp:
        def json(self):
            return payload

    class _Client:
        def __init__(self, **_kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def post(self, *_a, **_kw):
            return _Resp()

    with patch("httpx.AsyncClient", _Client):
        resp = client.post("/api/v1/observability/reliability-digest")

    assert resp.status_code == 200
    uptime = resp.json()["uptime"]
    assert uptime["status"] == "ok"
    assert uptime["monitors"][0]["uptime_7d"] == "100.000"
