"""Tests for the git-archive endpoint (GET /v1/jobs/daily-archive).

Covers the anonymization guarantee (no emails/user_ids ever leave the
API), the user-wise grouping with URL dedup across multiple sends, the
drop of malformed/legacy job cards, and the cron-secret gate.
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


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _ArchiveDB:
    """Returns the canned history rows for the endpoint's single select."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, stmt):  # noqa: ARG002
        return _ScalarsResult(self._rows)


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


def test_archive_groups_jobs_per_member_and_dedupes(client):
    from interntrack.api.v1.jobs_archive import _member_key

    db = _ArchiveDB(
        [
            # Same member twice (digest + catch-up) with an overlapping URL.
            _history_row("11111111-aaaa", [GOOD_CARD], ["grc"]),
            _history_row(
                "11111111-aaaa",
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
            _history_row("22222222-bbbb", [GOOD_CARD], ["grc"]),
        ]
    )
    client._use_db(db)  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()

    assert data["totals"]["members_with_jobs"] == 2
    assert data["totals"]["jobs_delivered"] == 3  # 2 for member A, 1 for B

    by_member = {m["member"]: m for m in data["members"]}
    assert len(by_member) == 2

    member_a = by_member[_member_key("11111111-aaaa")]
    assert member_a["job_count"] == 2  # deduped by URL
    urls = {j["url"] for j in member_a["jobs"]}
    assert urls == {"https://jobs.example.com/grc-1", "https://jobs.example.com/soc-2"}

    # Anonymization: raw user ids and any unknown card fields never leak.
    blob = resp.text
    assert "11111111" not in blob
    assert "22222222" not in blob
    assert "internal_id" not in blob
    assert all(m["member"].startswith("member-") for m in data["members"])

    # Sorted by volume (the 2-job member first).
    assert data["members"][0]["job_count"] == 2


def test_archive_drops_malformed_cards_and_empty_rows(client):
    db = _ArchiveDB(
        [
            _history_row(
                "33333333-cccc", ["not-a-dict", None, {"title": "", "url": "x"}]
            ),
            _history_row("44444444-dddd", [GOOD_CARD]),
            # Legacy row shape: jobs is not a list at all.
            SimpleNamespace(
                user_id="55555555-eeee", jobs="legacy", domains=[], created_at=None
            ),
            # No user_id — unusable, skipped.
            SimpleNamespace(user_id="", jobs=[GOOD_CARD], domains=[], created_at=None),
        ]
    )
    client._use_db(db)  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()

    # Only member 4 survived with its one clean card.
    assert data["totals"]["members_with_jobs"] == 1
    assert data["members"][0]["job_count"] == 1


def test_archive_empty_day_reports_zero(client):
    client._use_db(_ArchiveDB([]))  # type: ignore[attr-defined]

    resp = client.get("/api/v1/archive/daily-archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["members"] == []
    assert data["totals"] == {"members_with_jobs": 0, "jobs_delivered": 0}


def test_archive_member_key_is_stable_and_anonymous():
    from interntrack.api.v1.jobs_archive import _member_key

    key1 = _member_key("some-internal-uuid")
    key2 = _member_key("some-internal-uuid")
    assert key1 == key2  # deterministic across days/commits
    assert key1.startswith("member-")
    assert "some-internal-uuid" not in key1
    assert _member_key("other-uuid") != key1


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
