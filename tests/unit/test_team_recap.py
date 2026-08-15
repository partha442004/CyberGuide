"""
Unit tests for the weekly team-alerts recap (scheduler/jobs.py).

Covers the per-member history aggregation (``team_recap_stats``), the
HTML email builder (``_build_team_recap_html``) and the owner email job
(``send_team_recap``) including its silent-skip paths, the TEAM_OWNER_EMAIL
override, and the HTTP endpoint delegation.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _dt(days_ago: int) -> datetime:
    """Naive UTC timestamp ``days_ago`` days before now."""
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)

    def all(self):
        return self._items


def _user(uid, name, email="x@y.com", location="Bengaluru", domains=None):
    return SimpleNamespace(
        id=uid,
        name=name,
        email=email,
        location=location,
        domains=domains or [],
        created_at=_dt(30),
    )


def _history(
    uid, days_ago, job_count=1, results=None, domains=None, jobs=None, opened_at=None
):
    return SimpleNamespace(
        user_id=uid,
        created_at=_dt(days_ago),
        subject="Daily Report",
        job_count=job_count,
        results=results or {"email": True},
        domains=domains or [],
        jobs=jobs or [],
        opened_at=opened_at,
    )


class TestTeamRecapStats:
    """Per-member aggregation over a rolling window."""

    @pytest.mark.asyncio
    async def test_aggregates_per_member(self):
        from interntrack.scheduler.jobs import team_recap_stats

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _FakeResult(
                    [
                        _user("u1", "Boss", email="boss@x.com", domains=["security"]),
                        _user("u2", "Jeeva", email="jeeva@x.com", domains=["hardware"]),
                    ]
                ),
                _FakeResult(
                    [
                        _history(
                            "u2",
                            1,
                            job_count=3,
                            domains=["hardware"],
                            jobs=[
                                {"company": "ABB"},
                                {"company": "ABB"},
                                {"company": "Tata Elxsi"},
                            ],
                            opened_at=_dt(1),
                        ),
                        _history("u2", 2, job_count=2, domains=["hardware"], jobs=[]),
                        _history(
                            "u1",
                            1,
                            job_count=1,
                            results={"email": False},
                            domains=["security"],
                            jobs=[{"company": "Zscaler"}],
                        ),
                        # Outside the 7-day window — must be ignored.
                        _history("u2", 30, job_count=99, jobs=[]),
                    ]
                ),
                # Email apply clicks (user_id, count) — Jeeva applied to 3
                # jobs straight from her digest emails this week.
                _FakeResult([("u2", 3)]),
            ]
        )

        stats = await team_recap_stats(session, days=7)

        assert stats["days"] == 7
        assert stats["total_sends"] == 3
        assert stats["total_jobs"] == 6
        by_id = {u["user_id"]: u for u in stats["users"]}
        # Jeeva: 2 sends (the 30-day-old row is excluded), 5 jobs, both emails OK.
        jeeva = by_id["u2"]
        assert jeeva["sends"] == 2
        assert jeeva["jobs"] == 5
        assert jeeva["emails_ok"] == 2
        assert jeeva["opened"] == 1
        assert jeeva["email_applied"] == 3
        assert jeeva["top_domains"] == ["hardware"]
        assert jeeva["top_companies"] == ["ABB", "Tata Elxsi"]
        # Boss: 1 send, 1 job, email not delivered, never opened, no applies.
        boss = by_id["u1"]
        assert boss["sends"] == 1
        assert boss["jobs"] == 1
        assert boss["emails_ok"] == 0
        assert boss["opened"] == 0
        assert boss["email_applied"] == 0
        assert stats["total_email_applied"] == 3
        assert stats["total_opened"] == 1
        # Sorted by jobs desc — Jeeva first.
        assert stats["users"][0]["user_id"] == "u2"

    @pytest.mark.asyncio
    async def test_never_raises_on_bad_session(self):
        from interntrack.scheduler.jobs import team_recap_stats

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("db down"))

        stats = await team_recap_stats(session, days=7)

        assert stats["users"] == []
        assert stats["total_jobs"] == 0

    @pytest.mark.asyncio
    async def test_user_with_no_history_still_listed(self):
        from interntrack.scheduler.jobs import team_recap_stats

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _FakeResult([_user("u1", "Boss")]),
                _FakeResult([_history("u1", 1, job_count=2)]),
                _FakeResult([]),
            ]
        )

        stats = await team_recap_stats(session, days=7)

        assert len(stats["users"]) == 1
        assert stats["users"][0]["sends"] == 1
        assert stats["users"][0]["jobs"] == 2
        assert stats["users"][0]["email_applied"] == 0
        assert stats["users"][0]["opened"] == 0
        assert stats["total_email_applied"] == 0
        assert stats["total_opened"] == 0


class TestBuildTeamRecapHtml:
    """HTML builder escapes untrusted names/companies."""

    def test_renders_member_rows_and_summary(self):
        from interntrack.scheduler.jobs import _build_team_recap_html

        stats = {
            "total_jobs": 6,
            "total_sends": 3,
            "users": [
                {
                    "name": "Jeeva",
                    "email": "jeeva@x.com",
                    "location": "Chennai",
                    "domains": ["hardware"],
                    "top_domains": ["hardware"],
                    "top_companies": ["ABB", "Tata Elxsi"],
                    "sends": 2,
                    "jobs": 5,
                    "emails_ok": 2,
                },
                {
                    "name": "Boss",
                    "email": "boss@x.com",
                    "location": "Bengaluru",
                    "domains": ["security"],
                    "top_domains": [],
                    "top_companies": [],
                    "sends": 1,
                    "jobs": 1,
                    "emails_ok": 0,
                },
            ],
        }

        html = _build_team_recap_html(stats, "Boss")

        assert "Team alerts recap" in html
        assert "Jeeva" in html
        assert "ABB" in html
        assert "6" in html
        assert "3" in html
        # No top companies -> fallback dash.
        assert "🏢 —" in html

    def test_escapes_html_in_names_and_companies(self):
        from interntrack.scheduler.jobs import _build_team_recap_html

        stats = {
            "total_jobs": 1,
            "total_sends": 1,
            "users": [
                {
                    "name": "<script>alert(1)</script>",
                    "email": "a@b.com",
                    "location": "X",
                    "domains": [],
                    "top_domains": [],
                    "top_companies": ['"><img src=x>'],
                    "sends": 1,
                    "jobs": 1,
                    "emails_ok": 1,
                }
            ],
        }

        html = _build_team_recap_html(stats, "Owner")

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
        assert "<img src=x>" not in html
        assert "&lt;img" in html


class TestSendTeamRecap:
    """Owner email job: skips quietly, sends once, never raises."""

    def _settings(self, configured=True, owner_email=None):
        class _Settings:
            smtp_host = "smtp.test"
            smtp_port = 587
            smtp_user = "me@test"
            smtp_password = "pw"
            email_from = "InternTrack <noreply@test>"
            team_owner_email = owner_email
            team_recap_enabled = True

            @property
            def is_email_configured(self):
                return configured

        return _Settings()

    def _ctx(self, users):
        class _Ctx:
            async def __aenter__(self):
                return _FakeSession()

            async def __aexit__(self, *args):
                return False

        class _FakeSession:
            async def execute(self, stmt):  # noqa: ARG002
                return _FakeResult(users)

        return _Ctx()

    def _canned_stats(self):
        return {
            "days": 7,
            "total_sends": 3,
            "total_jobs": 6,
            "users": [
                {
                    "name": "Jeeva",
                    "email": "jeeva@x.com",
                    "location": "Chennai",
                    "domains": ["hardware"],
                    "top_domains": ["hardware"],
                    "top_companies": ["ABB"],
                    "sends": 2,
                    "jobs": 5,
                    "emails_ok": 2,
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_skips_when_disabled_by_default(self, monkeypatch):
        """TEAM_RECAP_ENABLED is off by default — no recap email may fire."""
        from interntrack.scheduler import jobs as jobs_mod

        sent = []

        class _FakeEmailChannel:
            def __init__(self, **kwargs):
                sent.append(kwargs.get("to_email"))

            async def send(self, message, subject=None):  # noqa: ARG002
                sent.append(subject)

        class _OffSettings:
            smtp_user = "me@test"
            smtp_password = "pw"
            team_recap_enabled = False

        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx(
                [
                    _user("u1", "Boss", email="boss@x.com"),
                    _user("u2", "Jeeva", email="jeeva@x.com"),
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _OffSettings(),
        )

        result = await jobs_mod.send_team_recap()

        assert sent == []
        assert result["sent"] is False
        assert "disabled" in result["reason"]

    @pytest.mark.asyncio
    async def test_skips_when_fewer_than_two_accounts(self, monkeypatch):
        from interntrack.scheduler import jobs as jobs_mod

        sent = []

        class _FakeEmailChannel:
            def __init__(self, **kwargs):
                sent.append(kwargs.get("to_email"))

            async def send(self, message, subject=None):  # noqa: ARG002
                sent.append(subject)

        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx([_user("u1", "Solo")]),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: self._settings(),
        )

        result = await jobs_mod.send_team_recap()

        assert sent == []
        assert result["sent"] is False
        assert result["reason"] == "need at least 2 accounts"

    @pytest.mark.asyncio
    async def test_sends_one_email_to_first_registered_owner(self, monkeypatch):
        from interntrack.scheduler import jobs as jobs_mod

        sent = []

        class _FakeEmailChannel:
            def __init__(self, **kwargs):
                sent.append(kwargs)

            async def send(self, message, subject=None):
                sent.append({"subject": subject, "html": message})

        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx(
                [
                    _user("u1", "Boss", email="boss@x.com"),
                    _user("u2", "Jeeva", email="jeeva@x.com"),
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: self._settings(),
        )
        monkeypatch.setattr(
            jobs_mod,
            "team_recap_stats",
            AsyncMock(return_value=self._canned_stats()),
        )

        result = await jobs_mod.send_team_recap()

        assert result["sent"] is True
        assert result["to"] == "boss@x.com"
        assert len(sent) == 2  # constructor kwargs + send call
        assert sent[0]["to_email"] == "boss@x.com"
        assert sent[1]["subject"].startswith("📬 Team alerts recap")
        assert "Jeeva" in sent[1]["html"]

    @pytest.mark.asyncio
    async def test_owner_override_wins(self, monkeypatch):
        from interntrack.scheduler import jobs as jobs_mod

        sent = []

        class _FakeEmailChannel:
            def __init__(self, **kwargs):
                sent.append(kwargs.get("to_email"))

            async def send(self, message, subject=None):  # noqa: ARG002
                pass

        # Jeeva registered first, but TEAM_OWNER_EMAIL names Skarkuzhali.
        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx(
                [
                    _user("u1", "Jeeva", email="jeeva@x.com"),
                    _user("u2", "Skarkuzhali", email="skarkuzhali@x.com"),
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: self._settings(owner_email="skarkuzhali@x.com"),
        )
        monkeypatch.setattr(
            jobs_mod,
            "team_recap_stats",
            AsyncMock(return_value=self._canned_stats()),
        )

        result = await jobs_mod.send_team_recap()

        assert result["sent"] is True
        assert result["to"] == "skarkuzhali@x.com"
        assert sent == ["skarkuzhali@x.com"]

    @pytest.mark.asyncio
    async def test_override_falls_back_to_first_registered(self, monkeypatch):
        """An override that matches no account must not lose the recap."""
        from interntrack.scheduler import jobs as jobs_mod

        sent = []

        class _FakeEmailChannel:
            def __init__(self, **kwargs):
                sent.append(kwargs.get("to_email"))

            async def send(self, message, subject=None):  # noqa: ARG002
                pass

        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx(
                [
                    _user("u1", "Boss", email="boss@x.com"),
                    _user("u2", "Jeeva", email="jeeva@x.com"),
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: self._settings(owner_email="ghost@x.com"),
        )
        monkeypatch.setattr(
            jobs_mod,
            "team_recap_stats",
            AsyncMock(return_value=self._canned_stats()),
        )

        result = await jobs_mod.send_team_recap()

        assert result["sent"] is True
        assert result["to"] == "boss@x.com"
        assert sent == ["boss@x.com"]

    @pytest.mark.asyncio
    async def test_skips_when_email_not_configured(self, monkeypatch):
        from interntrack.scheduler import jobs as jobs_mod

        sent = []

        class _FakeEmailChannel:
            def __init__(self, **kwargs):
                sent.append(kwargs)

            async def send(self, message, subject=None):  # noqa: ARG002
                sent.append(subject)

        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx(
                [
                    _user("u1", "Boss", email="boss@x.com"),
                    _user("u2", "Jeeva", email="jeeva@x.com"),
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: self._settings(configured=False),
        )

        result = await jobs_mod.send_team_recap()

        assert sent == []
        assert result["sent"] is False
        assert result["reason"] == "email not configured"

    @pytest.mark.asyncio
    async def test_never_raises_when_send_fails(self, monkeypatch):
        from interntrack.scheduler import jobs as jobs_mod

        class _FakeEmailChannel:
            def __init__(self, **kwargs):  # noqa: ARG002
                pass

            async def send(self, message, subject=None):  # noqa: ARG002
                raise RuntimeError("smtp down")

        monkeypatch.setattr(
            jobs_mod,
            "get_db_session",
            lambda: self._ctx(
                [
                    _user("u1", "Boss", email="boss@x.com"),
                    _user("u2", "Jeeva", email="jeeva@x.com"),
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.services.notification_service.EmailChannel",
            _FakeEmailChannel,
        )
        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: self._settings(),
        )
        monkeypatch.setattr(
            jobs_mod,
            "team_recap_stats",
            AsyncMock(return_value=self._canned_stats()),
        )

        # Must not raise despite the SMTP failure.
        result = await jobs_mod.send_team_recap()
        assert result["sent"] is False
        assert "smtp down" in result["reason"]


class TestOwnerEndpoint:
    """GET /notifications/owner resolves the admin account."""

    @pytest.mark.asyncio
    async def test_owner_override_wins(self, monkeypatch):
        from interntrack.api.v1.notifications import get_owner

        class _Cfg:
            team_owner_email = "boss@x.com"

        monkeypatch.setattr(
            "interntrack.api.v1.notifications.get_settings",
            lambda: _Cfg(),
        )

        result = await get_owner()

        assert result["email"] == "boss@x.com"
        assert result["is_owner"] is True

    @pytest.mark.asyncio
    async def test_owner_falls_back_to_first_registered(self, monkeypatch):
        from interntrack.api.v1.notifications import get_owner

        class _Cfg:
            team_owner_email = None

        monkeypatch.setattr(
            "interntrack.api.v1.notifications.get_settings",
            lambda: _Cfg(),
        )

        # First-registered account wins (oldest created_at).
        users = [
            _user("u1", "Boss", email="boss@x.com"),
            _user("u2", "Jeeva", email="jeeva@x.com"),
        ]

        class _FakeDb:
            async def execute(self, stmt):  # noqa: ARG002
                return _FakeResult(users)

        class _Gen:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return _FakeDb()

        monkeypatch.setattr(
            "interntrack.api.v1.notifications.get_db",
            lambda: _Gen(),
        )

        result = await get_owner()

        assert result["email"] == "boss@x.com"
        assert result["is_owner"] is True


class TestTeamRecapEndpoint:
    """GET /notifications/team/recap delegates to the shared stats."""

    @pytest.mark.asyncio
    async def test_endpoint_returns_stats(self, monkeypatch):
        from interntrack.api.v1.notifications import get_team_recap

        canned = {"days": 7, "total_sends": 3, "total_jobs": 6, "users": []}
        monkeypatch.setattr(
            "interntrack.scheduler.jobs.team_recap_stats",
            AsyncMock(return_value=canned),
        )

        result = await get_team_recap(days=7, db=AsyncMock())

        assert result == canned

    @pytest.mark.asyncio
    async def test_days_is_clamped(self, monkeypatch):
        from interntrack.api.v1.notifications import get_team_recap

        captured = {}

        async def _fake(db, days):
            captured["days"] = days
            return {"days": days, "users": []}

        monkeypatch.setattr("interntrack.scheduler.jobs.team_recap_stats", _fake)

        await get_team_recap(days=999, db=AsyncMock())

        assert captured["days"] == 30


class TestDeliveryOverview:
    """GET /notifications/delivery-overview reports last send per member."""

    @pytest.mark.asyncio
    async def test_reports_last_send_per_member(self, monkeypatch):
        from interntrack.api.v1.notifications import delivery_overview

        targets = [
            {
                "user_id": "u1",
                "user": _user(
                    "u1",
                    "Jeeva",
                    email="jeeva@x.com",
                    location="Chennai, Coimbatore",
                ),
                "prefs": {
                    "domains": ["hardware"],
                    "channels": ["email"],
                    "is_enabled": True,
                },
            }
        ]

        class _FakeDb:
            async def execute(self, stmt):  # noqa: ARG002
                return _FakeResult([_history("u1", 1, job_count=5)])

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            AsyncMock(return_value=targets),
        )

        result = await delivery_overview(db=_FakeDb())

        assert result["total"] == 1
        member = result["members"][0]
        assert member["email"] == "jeeva@x.com"
        assert member["location"] == "Chennai, Coimbatore"
        assert member["last_job_count"] == 5
        assert member["last_email_ok"] is True
        assert member["last_alert_at"] is not None

    @pytest.mark.asyncio
    async def test_never_sent_when_no_history(self, monkeypatch):
        from interntrack.api.v1.notifications import delivery_overview

        targets = [
            {
                "user_id": "u2",
                "user": _user("u2", "Panthal", email="p@x.com"),
                "prefs": {
                    "domains": ["data"],
                    "channels": ["email"],
                    "is_enabled": True,
                },
            }
        ]

        class _FakeDb:
            async def execute(self, stmt):  # noqa: ARG002
                return _FakeResult([])

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            AsyncMock(return_value=targets),
        )

        result = await delivery_overview(db=_FakeDb())

        member = result["members"][0]
        assert member["last_alert_at"] is None
        assert member["last_email_ok"] is None
        assert member["last_job_count"] == 0
        assert member["paused"] is False
