"""Tests for the git-archive endpoint (GET /v1/archive/daily-archive).

The archive document is committed into the SEPARATE PRIVATE repository,
so it carries real member identities resolved from the users table.
Covers identity resolution (and the anonymous fallback for profile-less
legacy ids), user-wise grouping with URL dedup across multiple sends,
the drop of malformed/legacy job cards, and the cron-secret gate.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def _history_row(user_id: str, jobs, domains=None):
    return SimpleNamespace(
        user_id=user_id,
        jobs=jobs,
        domains=domains or ["security"],
        created_at=None,
    )


def _user_row(user_id: str, name: str, email: str):
    return SimpleNamespace(id=user_id, name=name, email=email)


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _ArchiveDB:
    """Serves canned rows: select() keyed off the statement's entity."""

    def __init__(self, history_rows, user_rows=()):
        self._history = history_rows
        self._users = list(user_rows)

    async def execute(self, stmt):
        desc = str(getattr(stmt, "column_descriptions", "") or "")
        if "User" in desc:
            return _ScalarsResult(self._users)
        return _ScalarsResult(self._history)


@pytest.fixture
def client():
    from interntrack.database.session import get_db
    from interntrack.main import app

    overrides = []

    def _use(db):
        async def _supply():
            yield db

        app.dependency_overrides[get_db] = _supply
        overrides.append(get_db)

    client = TestClient(app, raise_server_exceptions=False)
    client._use_db = _use  # type: ignore[attr-defined]
    yield client
    for key in overrides:
        app.dependency_overrides.pop(key, None)


GOOD_CARD = {
    "title": "GRC Analyst",
    "company": "Acme Corp",
    "location": "Chennai",
    "url": "https://jobs.example.com/grc-1",
    "domain": "grc",
    "match_score": 82.0,
    "internal_id": "should-be-dropped",
}

UID_A = "11111111-aaaa"
UID_B = "22222222-bbbb"


def test_archive_resolves_real_identities_and_dedupes(client):
    db = _ArchiveDB(
        [
            # Same member twice (digest + catch-up) with an overlapping URL.
            _history_row(UID_A, [GOOD_CARD], ["grc"]),
            _history_row(
                UID_A,
                [
                    GOOD_CARD,
                    {
                        "title": "SOC Analyst",
                        "company": "Beta Ltd",
                        "location": "Remote",
                        "url": "https://jobs.example.com/soc-2",
                        "domain": "security",
                    },
                ],
                ["security"],
            ),
            # A second member keeps its own section.
            _history_row(UID_B, [GOOD_CARD], ["grc"]),
        ],
        [
            _user_row(UID_A, "Parthasarathi B", "partha@example.com"),
            _user_row(UID_B, "Swetha", "swetha@example.com"),
        ],
    )
    client._use_db(db)  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()

    assert data["totals"]["members_with_jobs"] == 2
    assert data["totals"]["jobs_delivered"] == 3  # 2 for A, 1 for B

    by_email = {m["email"]: m for m in data["members"]}
    assert set(by_email) == {"partha@example.com", "swetha@example.com"}

    member_a = by_email["partha@example.com"]
    assert member_a["name"] == "Parthasarathi B"
    assert member_a["job_count"] == 2  # deduped by URL
    urls = {j["url"] for j in member_a["jobs"]}
    assert urls == {"https://jobs.example.com/grc-1", "https://jobs.example.com/soc-2"}

    # Raw internal ids never leak even though identities do.
    blob = resp.text
    assert UID_A not in blob
    assert UID_B not in blob
    assert "internal_id" not in blob

    # Sorted by volume (the 2-job member first).
    assert data["members"][0]["job_count"] == 2


def test_archive_falls_back_to_anonymous_key_without_profile(client):
    db = _ArchiveDB(
        [_history_row("legacy-user1", [GOOD_CARD])],
        [_user_row(UID_A, "Someone", "someone@example.com")],
    )
    client._use_db(db)  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()

    assert data["totals"]["members_with_jobs"] == 1
    member = data["members"][0]
    assert member["email"] is None
    assert member["member"].startswith("unresolved-")
    # The raw legacy id is not exposed either.
    assert "legacy-user1" not in resp.text


def test_archive_drops_malformed_cards_and_empty_rows(client):
    db = _ArchiveDB(
        [
            _history_row(UID_A, ["not-a-dict", None, {"title": "", "url": "x"}]),
            _history_row(UID_B, [GOOD_CARD]),
            # Legacy row shape: jobs is not a list at all.
            SimpleNamespace(user_id=UID_A, jobs="legacy", domains=[], created_at=None),
            # No user_id — unusable, skipped.
            SimpleNamespace(user_id="", jobs=[GOOD_CARD], domains=[], created_at=None),
        ],
        [
            _user_row(UID_A, "A", "a@example.com"),
            _user_row(UID_B, "B", "b@example.com"),
        ],
    )
    client._use_db(db)  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()

    # Only member B survived with its one clean card.
    assert data["totals"]["members_with_jobs"] == 1
    assert data["members"][0]["job_count"] == 1


def test_archive_empty_day_reports_zero(client):
    client._use_db(_ArchiveDB([]))  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["members"] == []
    assert data["totals"] == {"members_with_jobs": 0, "jobs_delivered": 0}


def test_archive_fallback_key_is_stable_and_anonymous():
    from interntrack.api.v1.jobs_archive import _member_fallback_key

    key1 = _member_fallback_key("some-internal-uuid")
    key2 = _member_fallback_key("some-internal-uuid")
    assert key1 == key2  # deterministic across days/commits
    assert key1.startswith("unresolved-")
    assert "some-internal-uuid" not in key1
    assert _member_fallback_key("other-uuid") != key1


def test_archive_requires_cron_secret_when_configured(client, monkeypatch):
    from interntrack.config import get_settings

    if not hasattr(get_settings, "cache_clear"):
        pytest.skip("get_settings is not cached; guard test needs cache reset")
    monkeypatch.setenv("CRON_SECRET", "test-secret-123")
    get_settings.cache_clear()
    try:
        client._use_db(_ArchiveDB([]))  # type: ignore[attr-defined]
        assert client.get("/api/v1/archive/daily-archive").status_code == 401
        ok = client.get(
            "/api/v1/archive/daily-archive",
            headers={"X-Cron-Secret": "test-secret-123"},
        )
        assert ok.status_code == 200
    finally:
        get_settings.cache_clear()


def test_archive_window_math():
    from interntrack.api.v1.jobs_archive import _window_start

    now = __import__("datetime").datetime(2026, 9, 22, 7, 30)
    # days=1 -> UTC midnight today (exactly today's sends).
    assert _window_start(1, now) == __import__("datetime").datetime(2026, 9, 22)
    # days=7 -> midnight 6 days back (7 calendar days inclusive of today).
    assert _window_start(7, now) == __import__("datetime").datetime(2026, 9, 16)
