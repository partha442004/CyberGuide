"""Tests for the member self-service preferences pages and actions.

Covers the signed-link gate (bad tokens never reach data), the prefs save
flow (domains/cities/experience/skills), pause/resume, unsubscribe, and the
DPDP data-deletion path — through the FastAPI dependency-overrides mechanism
so routing, form parsing and redirects are exercised for real.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from interntrack.utils.helpers import prefs_token, verify_prefs_token


def _member(**overrides):
    base = {
        "id": "u-self",
        "name": "Test Member",
        "email": "member@test.com",
        "domains": ["security"],
        "skills": ["python"],
        "location": "Bangalore",
        "experience_level": "fresher",
        "is_active": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _prefs_row(enabled=True):
    return SimpleNamespace(user_id="u-self", is_enabled=enabled, channels=["email"])


class _Result:
    def __init__(self, scalar):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _FakeDB:
    """Records commits/deletes; select() keyed off the statement's entity."""

    def __init__(self, member, prefs):
        self._member = member
        self._prefs = prefs
        self.commits = 0
        self.deleted = []

    async def execute(self, stmt):
        desc = str(getattr(stmt, "column_descriptions", "") or "")
        if "AlertPreferences" in desc:
            return _Result(self._prefs)
        return _Result(self._member)

    async def commit(self):
        self.commits += 1

    async def delete(self, obj):
        self.deleted.append(obj)

    def add(self, obj):  # noqa: ARG002
        pass


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


# ---------------------------------------------------------------------------
# Token helper


class TestPrefsToken:
    def test_token_binds_user(self):
        tok = prefs_token("u1")
        assert verify_prefs_token("u1", tok)
        assert not verify_prefs_token("u2", tok)

    def test_bad_token_rejected(self):
        assert not verify_prefs_token("u1", "")
        assert not verify_prefs_token("u1", "0" * 64)
        assert not verify_prefs_token("u1", prefs_token("u1")[:-1] + "0")


# ---------------------------------------------------------------------------
# GET page


class TestPrefsPage:
    def test_bad_token_shows_link_not_valid(self, client):
        r = client.get(
            "/api/v1/self-service/prefs", params={"u": "u-self", "t": "0" * 64}
        )
        assert r.status_code == 200
        assert "Link not valid" in r.text

    def test_valid_token_renders_form(self, client):
        client._use_db(_FakeDB(_member(), _prefs_row()))  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.get("/api/v1/self-service/prefs", params={"u": "u-self", "t": tok})
        assert r.status_code == 200
        assert "Manage your alerts" in r.text
        assert "Test Member" in r.text
        assert "Bangalore" in r.text

    def test_inactive_member_locked_out(self, client):
        client._use_db(_FakeDB(_member(is_active=False), _prefs_row()))  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.get("/api/v1/self-service/prefs", params={"u": "u-self", "t": tok})
        assert "Link not valid" in r.text


# ---------------------------------------------------------------------------
# POST actions


class TestPrefsSave:
    def test_save_updates_member_and_redirects(self, client):
        db = _FakeDB(_member(), _prefs_row())
        client._use_db(db)  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.post(
            "/api/v1/self-service/prefs",
            params={"u": "u-self", "t": tok},
            data={
                "domains": ["grc", "security"],
                "cities": ["Chennai", "Salem"],
                "experience": "junior",
                "skills": "iso 27001, soc 2",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert db._member.domains == ["grc", "security"]
        assert db._member.location == "Chennai, Salem"
        assert db._member.experience_level == "junior"
        assert db._member.skills == ["iso 27001", "soc 2"]
        assert db.commits == 1

    def test_save_with_bad_token_never_touches_data(self, client):
        db = _FakeDB(_member(), _prefs_row())
        client._use_db(db)  # type: ignore[attr-defined]
        r = client.post(
            "/api/v1/self-service/prefs",
            params={"u": "u-self", "t": "f" * 64},
            data={"domains": ["grc"]},
            follow_redirects=False,
        )
        assert r.status_code == 200
        assert "Link not valid" in r.text
        assert db._member.domains == ["security"]  # unchanged
        assert db.commits == 0

    def test_save_drops_unknown_domains_and_cities(self, client):
        db = _FakeDB(_member(), _prefs_row())
        client._use_db(db)  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        client.post(
            "/api/v1/self-service/prefs",
            params={"u": "u-self", "t": tok},
            data={"domains": ["security", "hackers"], "cities": ["Chennai", "Mars"]},
            follow_redirects=False,
        )
        assert db._member.domains == ["security"]
        assert db._member.location == "Chennai"


class TestPauseResume:
    @pytest.mark.parametrize(
        ("op", "enabled_after", "saved"),
        [("pause", False, "paused"), ("resume", True, "resumed")],
    )
    def test_pause_and_resume(self, client, op, enabled_after, saved):
        db = _FakeDB(_member(), _prefs_row(enabled=not enabled_after))
        client._use_db(db)  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.post(
            "/api/v1/self-service/pause",
            params={"u": "u-self", "t": tok, "op": op},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert f"saved={saved}" in r.headers["location"]
        assert db._prefs.is_enabled is enabled_after

    def test_pause_creates_missing_prefs_row(self, client):
        db = _FakeDB(_member(), None)
        client._use_db(db)  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.post(
            "/api/v1/self-service/pause",
            params={"u": "u-self", "t": tok, "op": "pause"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert db.commits == 1


class TestUnsubscribe:
    def test_unsubscribe_disables_alerts_and_email_channel(self, client):
        db = _FakeDB(_member(), _prefs_row())
        client._use_db(db)  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.post(
            "/api/v1/self-service/unsubscribe",
            params={"u": "u-self", "t": tok},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "saved=unsub" in r.headers["location"]
        assert db._member.is_active is False
        assert db._prefs.is_enabled is False
        assert "email" not in (db._prefs.channels or [])


class TestDeleteMe:
    def test_delete_removes_member_and_history(self, client):
        db = _FakeDB(_member(), _prefs_row())
        client._use_db(db)  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.post(
            "/api/v1/self-service/delete",
            params={"u": "u-self", "t": tok},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "saved=deleted" in r.headers["location"]
        assert db.deleted, "member row must be deleted via session.delete"
        assert db.deleted[0] is db._member

    def test_delete_page_confirms(self, client):
        client._use_db(_FakeDB(_member(), _prefs_row()))  # type: ignore[attr-defined]
        tok = prefs_token("u-self")
        r = client.get(
            "/api/v1/self-service/prefs",
            params={"u": "u-self", "t": tok, "saved": "deleted"},
        )
        assert "Account deleted" in r.text


# ---------------------------------------------------------------------------
# Footer link integration


class TestFooterLink:
    def test_member_footer_embeds_signed_link(self, monkeypatch):
        from interntrack.config import get_settings
        from interntrack.scheduler.jobs import _member_footer_html

        monkeypatch.setenv("API_BASE_URL", "https://api.test")
        get_settings.cache_clear()
        try:
            html = _member_footer_html(user_id="u-foot")
        finally:
            get_settings.cache_clear()
        assert "/api/v1/self-service/prefs?u=u-foot&t=" in html
        assert "Manage your alerts" in html

    def test_member_footer_without_user_keeps_admin_text(self):
        from interntrack.scheduler.jobs import _member_footer_html

        html = _member_footer_html()
        assert "self-service" not in html
        assert "ask your admin" in html
