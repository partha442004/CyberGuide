"""
Tests for daily-alert preferences: the model-backed preference loader,
preferences API endpoints (get / upsert / send-alert), domain filtering in
the report service, and match-threshold filtering in the alert message.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _db_with_row(row) -> AsyncMock:
    """Session mock whose execute() returns a result exposing the row."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result)
    return mock_db


# ---------------------------------------------------------------------------
# _load_alert_preferences
# ---------------------------------------------------------------------------


class TestLoadAlertPreferences:
    """Preference loader used by the scheduler and the API."""

    @pytest.mark.asyncio
    async def test_no_row_returns_defaults(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        assert await _load_alert_preferences(_db_with_row(None)) == {}

    @pytest.mark.asyncio
    async def test_disabled_row_keeps_values_with_flag(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.is_enabled = False
        row.domains = ["security"]
        row.channels = []
        row.min_match_score = None
        row.last_alert_at = None
        row.slot_domains = None
        row.weekly_enabled = True
        row.instant_alerts = None
        row.include_remote = None
        row.paused_until = None
        row.min_salary = None
        row.keywords = None

        prefs = await _load_alert_preferences(_db_with_row(row))
        assert prefs == {
            "domains": ["security"],
            "channels": [],
            "min_match_score": None,
            "is_enabled": False,
            "last_alert_at": None,
            "slot_domains": {},
            "weekly_enabled": True,
            "instant_alerts": True,
            "include_remote": True,
            "quiet_day_emails": True,
            "paused_until": None,
            "min_salary": None,
            "keywords": [],
            "experience_levels": [],
        }

    @pytest.mark.asyncio
    async def test_enabled_row_returns_prefs(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.is_enabled = True
        row.domains = ["security"]
        row.channels = ["email"]
        row.min_match_score = 60
        row.last_alert_at = None
        row.slot_domains = {"morning": ["security"]}
        row.weekly_enabled = False
        row.instant_alerts = True
        row.include_remote = False
        row.paused_until = None
        row.min_salary = None
        row.keywords = []

        prefs = await _load_alert_preferences(_db_with_row(row))
        assert prefs == {
            "domains": ["security"],
            "channels": ["email"],
            "min_match_score": 60,
            "is_enabled": True,
            "last_alert_at": None,
            "slot_domains": {"morning": ["security"]},
            "instant_alerts": True,
            "include_remote": False,
            "quiet_day_emails": True,
            "weekly_enabled": False,
            "paused_until": None,
            "min_salary": None,
            "keywords": [],
            "experience_levels": [],
        }

    @pytest.mark.asyncio
    async def test_loads_prefs_for_given_user(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.is_enabled = True
        row.domains = ["coding"]
        row.channels = []
        row.min_match_score = None
        row.slot_domains = None
        row.weekly_enabled = True

        prefs = await _load_alert_preferences(_db_with_row(row), user_id="user2")
        assert prefs["domains"] == ["coding"]
        assert prefs["slot_domains"] == {}
        assert prefs["weekly_enabled"] is True

    @pytest.mark.asyncio
    async def test_never_raises_on_db_error(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("db down")

        assert await _load_alert_preferences(mock_db) == {}

    @pytest.mark.asyncio
    async def test_scheduler_skips_digest_when_disabled(self):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        mock_report_service = MagicMock()
        mock_manager = MagicMock()
        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["security"],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": False,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs.ReportService",
                return_value=mock_report_service,
            ),
            patch(
                "interntrack.scheduler.jobs.NotificationManager",
                return_value=mock_manager,
            ),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            await generate_daily_report()

        mock_report_service.generate_daily_report.assert_not_called()
        mock_manager.notify_all.assert_not_called()
        mock_manager.notify.assert_not_called()


# ---------------------------------------------------------------------------
# Preferences API
# ---------------------------------------------------------------------------


class TestPreferencesAPI:
    """GET / PUT / send-alert endpoints."""

    @pytest.mark.asyncio
    async def test_get_preferences_defaults(self):
        from interntrack.api.v1.notifications import get_alert_preferences

        with patch(
            "interntrack.api.v1.notifications._load_alert_preferences",
            new=AsyncMock(return_value={}),
        ):
            result = await get_alert_preferences("user1", db=AsyncMock())

        assert result.user_id == "user1"
        assert result.domains == []
        assert result.channels == []
        assert result.min_match_score is None
        assert result.is_enabled is True

    @pytest.mark.asyncio
    async def test_get_preferences_returns_saved_values(self):
        from interntrack.api.v1.notifications import get_alert_preferences

        with patch(
            "interntrack.api.v1.notifications._load_alert_preferences",
            new=AsyncMock(
                return_value={
                    "domains": ["security"],
                    "channels": ["email"],
                    "min_match_score": 60,
                    "is_enabled": True,
                }
            ),
        ):
            result = await get_alert_preferences("user1", db=AsyncMock())

        assert result.domains == ["security"]
        assert result.channels == ["email"]
        assert result.min_match_score == 60
        assert result.is_enabled is True

    @pytest.mark.asyncio
    async def test_get_preferences_reports_disabled(self):
        from interntrack.api.v1.notifications import get_alert_preferences

        with patch(
            "interntrack.api.v1.notifications._load_alert_preferences",
            new=AsyncMock(
                return_value={
                    "domains": ["security"],
                    "channels": [],
                    "min_match_score": None,
                    "is_enabled": False,
                }
            ),
        ):
            result = await get_alert_preferences("user1", db=AsyncMock())

        assert result.is_enabled is False
        assert result.domains == ["security"]

    @pytest.mark.asyncio
    async def test_update_preferences_creates_row(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        mock_db = _db_with_row(None)

        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(
                domains=["security", "bogus-domain"],
                channels=["email", "pigeon"],
                min_match_score=60,
            ),
            db=mock_db,
        )

        assert result.domains == ["security"]  # unknown domains dropped
        assert result.channels == ["email"]  # unknown channels dropped
        assert result.min_match_score == 60
        assert result.is_enabled is True

    @pytest.mark.asyncio
    async def test_update_preferences_upserts_existing(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences
        from interntrack.domain.models import AlertPreferences

        existing = AlertPreferences(user_id="user1", domains=["coding"])
        mock_db = _db_with_row(existing)

        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(domains=["security"]),
            db=mock_db,
        )

        assert existing.domains == ["security"]  # updated in place
        assert result.domains == ["security"]

    @pytest.mark.asyncio
    async def test_update_clamps_min_match_score(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        mock_db = _db_with_row(None)

        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(min_match_score=250),
            db=mock_db,
        )
        assert result.min_match_score == 100

    @pytest.mark.asyncio
    async def test_update_saves_slot_domains_and_weekly_enabled(self):
        """Per-slot categories + weekly toggle persist through the API."""
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        mock_db = _db_with_row(None)
        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(
                slot_domains={
                    "morning": ["security"],
                    "afternoon": ["coding", "bogus"],
                    "midnight": ["data"],  # unknown slot dropped
                },
                weekly_enabled=False,
            ),
            db=mock_db,
        )

        assert result.slot_domains == {
            "morning": ["security"],
            "afternoon": ["coding"],
        }
        assert result.weekly_enabled is False

    @pytest.mark.asyncio
    async def test_get_preferences_includes_slot_fields(self):
        from interntrack.api.v1.notifications import get_alert_preferences

        with patch(
            "interntrack.api.v1.notifications._load_alert_preferences",
            new=AsyncMock(
                return_value={
                    "domains": ["security"],
                    "channels": ["email"],
                    "min_match_score": None,
                    "is_enabled": True,
                    "slot_domains": {"morning": ["security"]},
                    "weekly_enabled": True,
                }
            ),
        ):
            result = await get_alert_preferences("user1", db=AsyncMock())

        assert result.slot_domains == {"morning": ["security"]}
        assert result.weekly_enabled is True

    @pytest.mark.asyncio
    async def test_get_preferences_defaults_instant_alerts_on(self):
        """instant_alerts defaults to True even when the DB row lacks it."""
        from interntrack.api.v1.notifications import get_alert_preferences

        with patch(
            "interntrack.api.v1.notifications._load_alert_preferences",
            new=AsyncMock(return_value={}),
        ):
            result = await get_alert_preferences("user1", db=AsyncMock())

        assert result.instant_alerts is True

    @pytest.mark.asyncio
    async def test_update_saves_instant_alerts_flag(self):
        """The instant Telegram ping toggle persists through the API."""
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        mock_db = _db_with_row(None)
        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(instant_alerts=False),
            db=mock_db,
        )

        assert result.instant_alerts is False

    @pytest.mark.asyncio
    async def test_send_alert_filters_and_notifies_preferred_channels(self):
        from interntrack.api.v1.notifications import send_alert_now

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {
                    "new_jobs": 2,
                    "new_applications": 0,
                    "total_applications": 0,
                },
                "new_jobs": [{}, {}],
            }
        )
        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(return_value={"email": True})
        mock_manager.notify_all = AsyncMock(return_value={"telegram": True})
        mock_manager.get_configured_channels.return_value = ["email"]

        with (
            patch(
                "interntrack.api.v1.notifications._load_alert_preferences",
                new=AsyncMock(
                    return_value={"domains": ["security"], "channels": ["email"]}
                ),
            ),
            patch(
                "interntrack.api.v1.notifications.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.notifications.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="filtered message"),
            ),
        ):
            result = await send_alert_now("user1", db=mock_db)

        assert result["job_count"] == 2
        assert result["results"] == {"email": True}
        assert result["domains"] == ["security"]
        mock_service.generate_daily_report.assert_called_once_with(
            domains=["security"],
            min_match_score=None,
            since=None,
            location="Bangalore",
            include_remote=True,
            experience_levels=None,
        )
        # Preferred channels (email) used, not notify_all.
        mock_manager.notify.assert_awaited_once_with(
            ["email"], "filtered message", subject="InternTrack Daily Alert (security)"
        )
        mock_manager.notify_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_falls_back_to_all_channels(self):
        from interntrack.api.v1.notifications import send_alert_now

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {
                    "new_jobs": 0,
                    "new_applications": 0,
                    "total_applications": 0,
                },
                "new_jobs": [],
            }
        )
        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(return_value={"telegram": True})
        mock_manager.notify_all = AsyncMock(return_value={"telegram": True})
        mock_manager.get_configured_channels.return_value = ["telegram"]

        with (
            patch(
                "interntrack.api.v1.notifications._load_alert_preferences",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "interntrack.api.v1.notifications.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.notifications.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs.build_daily_report_message",
                new=AsyncMock(return_value="msg"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk", [])]),
            ),
        ):
            result = await send_alert_now("user1", db=mock_db)

        assert result["results"] == {"telegram": True}
        assert result["domains"] == []
        mock_manager.notify.assert_awaited_once_with(
            ["telegram"], "chunk", subject="InternTrack Daily Alert", buttons=[]
        )
        mock_manager.notify_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_one_off_override_without_saving(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import send_alert_now

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {
                    "new_jobs": 3,
                    "new_applications": 0,
                    "total_applications": 0,
                },
                "new_jobs": [{}, {}, {}],
            }
        )
        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(return_value={"telegram": True})
        mock_manager.get_configured_channels.return_value = ["telegram"]
        recorder = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.notifications._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["security"],
                        "channels": ["email"],
                        "is_enabled": True,
                    }
                ),
            ),
            patch(
                "interntrack.api.v1.notifications.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.notifications.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs.build_daily_report_message",
                new=AsyncMock(return_value="msg"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk", [("Apply", "https://x")])]),
            ),
            patch(
                "interntrack.api.v1.notifications._record_alert_history",
                new=recorder,
            ),
        ):
            result = await send_alert_now(
                "user1",
                override=AlertPreferencesUpdate(
                    domains=["coding"],
                    channels=["telegram"],
                ),
                db=mock_db,
            )

        # Override used for this one send only.
        assert result["domains"] == ["coding"]
        mock_service.generate_daily_report.assert_called_once_with(
            domains=["coding"],
            min_match_score=None,
            since=None,
            location="Bangalore",
            include_remote=True,
            experience_levels=None,
        )
        mock_manager.notify.assert_awaited_once_with(
            ["telegram"],
            "chunk",
            subject="InternTrack Daily Alert (coding)",
            buttons=[("Apply", "https://x")],
        )
        recorder.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_alert_overrides_min_match_score(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import send_alert_now

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {
                    "new_jobs": 0,
                    "new_applications": 0,
                    "total_applications": 0,
                },
                "new_jobs": [],
            }
        )
        mock_manager = MagicMock()
        mock_manager.notify_all = AsyncMock(return_value={})

        with (
            patch(
                "interntrack.api.v1.notifications._load_alert_preferences",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "interntrack.api.v1.notifications.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.notifications.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs.build_daily_report_message",
                new=AsyncMock(return_value="msg"),
            ),
            patch(
                "interntrack.api.v1.notifications._record_alert_history",
                new=AsyncMock(),
            ),
        ):
            await send_alert_now(
                "user1",
                override=AlertPreferencesUpdate(min_match_score=85),
                db=mock_db,
            )

        mock_service.generate_daily_report.assert_called_once_with(
            domains=None,
            min_match_score=85,
            since=None,
            location="Bangalore",
            include_remote=True,
            experience_levels=None,
        )


# ---------------------------------------------------------------------------
# Alert history
# ---------------------------------------------------------------------------


class TestAlertHistory:
    """History endpoint and recording helper."""

    @pytest.mark.asyncio
    async def test_history_endpoint_returns_rows(self):
        from datetime import datetime

        from interntrack.api.v1.notifications import get_alert_history
        from interntrack.domain.models import NotificationHistory

        row = NotificationHistory(
            user_id="user1",
            subject="InternTrack Daily Alert (security)",
            channels=["email"],
            domains=["security"],
            job_count=5,
            results={"email": True},
            created_at=datetime(2026, 8, 5, 7, 0, 0),
        )
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [row]
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=result_mock)

        data = await get_alert_history("user1", db=mock_db)

        assert data["total"] == 1
        entry = data["history"][0]
        assert entry["domains"] == ["security"]
        assert entry["channels"] == ["email"]
        assert entry["job_count"] == 5
        assert entry["results"] == {"email": True}
        assert entry["sent_at"] is not None

    @pytest.mark.asyncio
    async def test_history_endpoint_returns_jobs(self):
        from datetime import datetime

        from interntrack.api.v1.notifications import get_alert_history
        from interntrack.domain.models import NotificationHistory

        row = NotificationHistory(
            user_id="user1",
            subject="Daily Report (security)",
            channels=["email"],
            domains=["security"],
            job_count=1,
            results={"email": True},
            jobs=[
                {
                    "title": "Cybersecurity Analyst",
                    "company": "Acme",
                    "location": "Bangalore",
                    "url": "https://x/job",
                    "domain": "security",
                    "match_score": 87.0,
                }
            ],
            created_at=datetime(2026, 8, 5, 7, 0, 0),
        )
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [row]
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=result_mock)

        data = await get_alert_history("user1", db=mock_db)
        jobs = data["history"][0]["jobs"]
        assert jobs[0]["title"] == "Cybersecurity Analyst"
        assert jobs[0]["match_score"] == 87.0
        assert jobs[0]["url"] == "https://x/job"

    @pytest.mark.asyncio
    async def test_history_endpoint_empty(self):
        from interntrack.api.v1.notifications import get_alert_history

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=result_mock)

        data = await get_alert_history("user1", db=mock_db)
        assert data == {"history": [], "total": 0}

    @pytest.mark.asyncio
    async def test_record_history_never_raises(self):
        from interntrack.scheduler.jobs import _record_alert_history

        mock_db = AsyncMock()
        mock_db.commit.side_effect = RuntimeError("db down")

        # Must not raise even when the commit fails.
        await _record_alert_history(
            mock_db,
            "user1",
            "InternTrack Daily Alert",
            ["email"],
            ["security"],
            3,
            {"email": True},
        )

    @pytest.mark.asyncio
    async def test_record_history_stores_jobs(self):
        from interntrack.scheduler.jobs import _record_alert_history

        mock_db = AsyncMock()
        await _record_alert_history(
            mock_db,
            "user1",
            "Daily Report (security)",
            ["email"],
            ["security"],
            2,
            {"email": True},
            jobs=[
                {
                    "title": "SOC Analyst",
                    "company": "X Corp",
                    "match_score": 92.0,
                }
            ],
        )
        added = mock_db.add.call_args[0][0]
        assert added.jobs[0]["title"] == "SOC Analyst"
        assert added.jobs[0]["match_score"] == 92.0

    @pytest.mark.asyncio
    async def test_preview_digest_returns_jobs_no_send(self):
        from interntrack.api.v1.notifications import preview_digest

        job = {
            "id": "j1",
            "title": "Cybersecurity Analyst",
            "company": "Acme",
            "location": "Bangalore",
            "url": "https://x",
            "domain": "security",
            "posted_at": "2026-08-05 07:00:00",
        }
        report = {
            "new_jobs": [job],
            "summary": {"new_jobs": 1},
            "min_match_score": None,
        }
        mock_service = AsyncMock()
        mock_service.generate_daily_report = AsyncMock(return_value=report)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        with (
            patch(
                "interntrack.api.v1.notifications._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["security"],
                        "channels": ["email"],
                        "min_match_score": None,
                        "last_alert_at": None,
                        "include_remote": True,
                    }
                ),
            ),
            patch(
                "interntrack.api.v1.notifications.ReportService",
                new=MagicMock(return_value=mock_service),
            ),
            patch(
                "interntrack.api.v1.notifications._latest_resume_skill_names",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "interntrack.api.v1.notifications._job_match_score",
                new=lambda *_args: 87.5,
            ),
        ):
            data = await preview_digest("user1", db=mock_db)

        assert data["job_count"] == 1
        assert data["jobs"][0]["title"] == "Cybersecurity Analyst"
        assert data["jobs"][0]["match_score"] == 87.5
        assert data["jobs"][0]["domain"] == "security"
        # Preview must never call the delivery path.
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Report service domain filtering
# ---------------------------------------------------------------------------


class _MockJob:
    """Minimal job stand-in matching the repo contract."""

    def __init__(
        self,
        title="Job",
        company="Acme",
        job_id="j1",
        created_at=None,
    ):
        self.title = title
        self.company = company
        self.location = "Remote"
        self.url = "https://x"
        self.expires_at = None
        self.created_at = created_at
        self.posted_at = None
        self.is_active = True
        self.id = job_id
        self.tags = None


class TestReportDomainFilter:
    """generate_daily_report honors the domains argument."""

    @pytest.mark.asyncio
    async def test_filters_jobs_by_domain(self):
        from interntrack.services.report_service import ReportService

        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(title="Security Analyst", job_id="j1"),
            _MockJob(title="Senior Python Developer", job_id="j2"),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report(domains=["security"])

        assert len(report["new_jobs"]) == 1
        assert report["new_jobs"][0]["domain"] == "security"
        assert report["summary"]["new_jobs"] == 1
        assert report["min_match_score"] is None

    @pytest.mark.asyncio
    async def test_no_domains_keeps_all(self):
        from interntrack.services.report_service import ReportService

        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(title="Security Analyst", job_id="j1"),
            _MockJob(title="Python Developer", job_id="j2"),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report()

        assert len(report["new_jobs"]) == 2

    @pytest.mark.asyncio
    async def test_filters_jobs_created_since_last_alert(self):
        """Only jobs created after the previous alert are included (no repeats)."""
        from datetime import timedelta

        from interntrack.services.report_service import ReportService

        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        now = datetime.now(UTC)
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(
                title="Already Sent", job_id="old", created_at=now - timedelta(days=1)
            ),
            _MockJob(title="Brand New", job_id="new", created_at=now),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report(
            since=now - timedelta(hours=2),
        )

        titles = [j["title"] for j in report["new_jobs"]]
        assert titles == ["Brand New"]
        assert report["summary"]["new_jobs"] == 1


# ---------------------------------------------------------------------------
# No-duplicates alert window
# ---------------------------------------------------------------------------


class TestAlertWindow:
    """last_alert_at window: mark sent + skip empty digests."""

    @pytest.mark.asyncio
    async def test_mark_alert_sent_creates_row(self):
        from interntrack.scheduler.jobs import _mark_alert_sent

        mock_db = _db_with_row(None)
        await _mark_alert_sent(mock_db, "user1")

        # A row was added to the session.
        added = list(mock_db.add.call_args_list)
        assert added
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_mark_alert_sent_updates_existing(self):
        from interntrack.scheduler.jobs import _mark_alert_sent

        existing = MagicMock()
        existing.is_enabled = True
        existing.last_alert_at = None
        mock_db = _db_with_row(existing)

        await _mark_alert_sent(mock_db, "user1")

        assert existing.last_alert_at is not None

    @pytest.mark.asyncio
    async def test_mark_alert_sent_never_raises(self):
        from interntrack.scheduler.jobs import _mark_alert_sent

        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("db down")

        await _mark_alert_sent(mock_db, "user1")

    @pytest.mark.asyncio
    async def test_scheduler_skips_send_when_no_new_jobs(self):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        mock_report_service = MagicMock()
        mock_report_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {
                    "new_jobs": 0,
                    "new_applications": 0,
                    "total_applications": 0,
                },
                "new_jobs": [],
            }
        )
        mock_manager = MagicMock()
        mock_manager.notify_all = AsyncMock(return_value={"telegram": True})

        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["security"],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": True,
                        "last_alert_at": None,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs.ReportService",
                return_value=mock_report_service,
            ),
            patch(
                "interntrack.scheduler.jobs.NotificationManager",
                return_value=mock_manager,
            ),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            await generate_daily_report()

        mock_report_service.generate_daily_report.assert_called_once_with(
            domains=["security"],
            min_match_score=None,
            since=None,
            location="Bangalore",
            include_remote=True,
            experience_levels=None,
        )
        mock_manager.notify_all.assert_not_called()
        mock_manager.notify.assert_not_called()


# ---------------------------------------------------------------------------
# Alert message: match threshold + domain footer
# ---------------------------------------------------------------------------


class TestAlertMessageFilter:
    """build_daily_report_message honors min_match_score and domains."""

    def _report(self):
        return {
            "summary": {"new_jobs": 2, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "a",
                    "title": "Security Analyst",
                    "company": "Acme",
                    "url": "https://a",
                    "domain": "security",
                    "is_applied": False,
                    "age_days": 0,
                },
                {
                    "id": "b",
                    "title": "Pentester",
                    "company": "Beta",
                    "url": "https://b",
                    "domain": "security",
                    "is_applied": False,
                    "age_days": 1,
                },
            ],
            "min_match_score": 70,
        }

    @pytest.mark.asyncio
    async def test_drops_jobs_below_match_threshold(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        with (
            patch(
                "interntrack.scheduler.jobs._latest_resume_skill_names",
                new=AsyncMock(return_value={"sql"}),
            ),
            patch(
                "interntrack.scheduler.jobs._job_match_score",
                side_effect=[80.0, 30.0],
            ),
        ):
            msg = await build_daily_report_message(self._report(), AsyncMock())

        assert "80%" in msg
        assert "30%" not in msg
        assert "Pentester" not in msg

    @pytest.mark.asyncio
    async def test_adds_domain_footer(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = self._report()
        report["min_match_score"] = None
        with (
            patch(
                "interntrack.scheduler.jobs._latest_resume_skill_names",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "interntrack.scheduler.jobs._job_match_score",
                side_effect=[None, None],
            ),
        ):
            msg = await build_daily_report_message(
                report, AsyncMock(), domains=["security"]
            )

        assert "🔔 Filtered to: security only" in msg
        assert "Security Analyst" in msg


class TestAlertChunks:
    """Telegram digest chunks carry inline Apply buttons per job."""

    def _report(self, n: int = 5) -> dict:
        return {
            "summary": {"new_jobs": n, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": f"j{i}",
                    "title": f"Security Job {i}",
                    "company": "Acme",
                    "url": f"https://apply/{i}",
                    "domain": "security",
                    "is_applied": False,
                    "age_days": 0,
                }
                for i in range(n)
            ],
            "min_match_score": None,
        }

    @pytest.mark.asyncio
    async def test_chunks_split_by_job_count(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        with (
            patch(
                "interntrack.scheduler.jobs._latest_resume_skill_names",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "interntrack.scheduler.jobs._job_match_score",
                side_effect=[None] * 5,
            ),
        ):
            chunks = await build_alert_chunks(self._report(5), AsyncMock())

        # 5 jobs at 4 per chunk -> 2 job chunks, plus the closing
        # role × location breakdown table as a final chunk.
        assert len(chunks) == 3
        assert len(chunks[0][1]) == 4  # 4 Apply buttons
        assert len(chunks[1][1]) == 1
        assert "Security Job 0" in chunks[0][0]
        assert "✅ Apply — Security Job 4" in chunks[1][1][0][0]
        assert chunks[1][1][0][1] == "https://apply/4"
        assert "Jobs by role × location" in chunks[2][0]

    @pytest.mark.asyncio
    async def test_empty_report_single_chunk_no_buttons(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        chunks = await build_alert_chunks({"summary": {}, "new_jobs": []}, AsyncMock())
        assert len(chunks) == 1
        assert chunks[0][1] == []
        assert "📊 Daily Report" in chunks[0][0]

    @pytest.mark.asyncio
    async def test_weekly_chunks_use_weekly_title(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        with (
            patch(
                "interntrack.scheduler.jobs._latest_resume_skill_names",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "interntrack.scheduler.jobs._job_match_score",
                side_effect=[None],
            ),
        ):
            chunks = await build_alert_chunks(self._report(1), AsyncMock(), weekly=True)

        assert "📅 Weekly Digest" in chunks[0][0]

    @pytest.mark.asyncio
    async def test_deliver_alert_splits_email_and_telegram(self):
        """Email gets the full message; Telegram gets chunked Apply buttons."""
        from interntrack.scheduler.jobs import _deliver_alert

        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(
            side_effect=lambda channels, *_args, **_kwargs: {channels[0]: True}
        )
        report = self._report(2)

        with (
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="full email text"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk1", [("Apply", "https://x")])]),
            ),
        ):
            results = await _deliver_alert(
                mock_manager,
                ["email", "telegram"],
                report,
                AsyncMock(),
                domains=["security"],
                subject="Daily Report (security)",
            )

        assert results == {"email": True, "telegram": True}
        mock_manager.notify.assert_any_await(
            ["email"], "full email text", subject="Daily Report (security)"
        )
        mock_manager.notify.assert_any_await(
            ["telegram"],
            "chunk1",
            subject="Daily Report (security)",
            buttons=[("Apply", "https://x")],
        )

    async def test_email_retries_once_on_transient_failure(self):
        """A failed email send is retried once before the result is final."""
        from interntrack.scheduler.jobs import _deliver_alert

        calls = {"n": 0}

        async def _flaky_notify(channels, *_args, **_kwargs):
            calls["n"] += 1
            return {channels[0]: calls["n"] > 1}  # fail first, succeed retry

        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(side_effect=_flaky_notify)
        report = self._report(2)

        with (
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="full email text"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[]),
            ),
            patch("interntrack.scheduler.jobs.asyncio.sleep", new=AsyncMock()),
        ):
            results = await _deliver_alert(
                mock_manager,
                ["email"],
                report,
                AsyncMock(),
                domains=["security"],
            )

        assert results == {"email": True}
        assert calls["n"] == 2  # original + one retry

    async def test_email_no_retry_when_delivered(self):
        """A delivered email is never retried."""
        from interntrack.scheduler.jobs import _deliver_alert

        calls = {"n": 0}

        async def _ok_notify(channels, *_args, **_kwargs):
            calls["n"] += 1
            return {channels[0]: True}

        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(side_effect=_ok_notify)
        report = self._report(2)

        with (
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="full email text"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[]),
            ),
            patch("interntrack.scheduler.jobs.asyncio.sleep", new=AsyncMock()),
        ):
            results = await _deliver_alert(
                mock_manager,
                ["email"],
                report,
                AsyncMock(),
                domains=["security"],
            )

        assert results == {"email": True}
        assert calls["n"] == 1  # no retry on success


# ---------------------------------------------------------------------------
# Vacation mode (pause all alerts)
# ---------------------------------------------------------------------------


class TestAlertsPaused:
    """The ``_alerts_paused`` gate used by every delivery path."""

    def test_no_pause_is_not_paused(self):
        from interntrack.scheduler.jobs import _alerts_paused

        assert _alerts_paused({}) is False
        assert _alerts_paused({"paused_until": None}) is False

    def test_future_timestamp_is_paused(self):
        from datetime import timedelta

        from interntrack.scheduler.jobs import _alerts_paused
        from interntrack.utils.helpers import utcnow

        prefs = {"paused_until": utcnow() + timedelta(days=3)}
        assert _alerts_paused(prefs) is True

    def test_past_timestamp_is_not_paused(self):
        from datetime import timedelta

        from interntrack.scheduler.jobs import _alerts_paused
        from interntrack.utils.helpers import utcnow

        prefs = {"paused_until": utcnow() - timedelta(hours=1)}
        assert _alerts_paused(prefs) is False

    def test_garbage_timestamp_never_raises(self):
        from interntrack.scheduler.jobs import _alerts_paused

        assert _alerts_paused({"paused_until": "not-a-date"}) is False


class TestPauseAPI:
    """Pausing / resuming through the preferences API."""

    @pytest.mark.asyncio
    async def test_update_sets_paused_until(self):
        from datetime import timedelta

        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences
        from interntrack.utils.helpers import utcnow

        mock_db = _db_with_row(None)
        until = utcnow() + timedelta(days=7)
        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(paused_until=until),
            db=mock_db,
        )

        assert result.paused_until == until

    @pytest.mark.asyncio
    async def test_resume_alerts_clears_pause(self):
        from datetime import timedelta

        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences
        from interntrack.domain.models import AlertPreferences
        from interntrack.utils.helpers import utcnow

        existing = AlertPreferences(
            user_id="user1",
            paused_until=utcnow() + timedelta(days=3),
        )
        mock_db = _db_with_row(existing)

        result = await update_alert_preferences(
            "user1",
            AlertPreferencesUpdate(resume_alerts=True),
            db=mock_db,
        )

        assert existing.paused_until is None
        assert result.paused_until is None

    @pytest.mark.asyncio
    async def test_get_preferences_reports_paused_until(self):
        from interntrack.api.v1.notifications import get_alert_preferences

        with patch(
            "interntrack.api.v1.notifications._load_alert_preferences",
            new=AsyncMock(
                return_value={
                    "domains": [],
                    "channels": [],
                    "min_match_score": None,
                    "is_enabled": True,
                    "paused_until": datetime(2026, 12, 31, 0, 0, 0),
                }
            ),
        ):
            result = await get_alert_preferences("user1", db=AsyncMock())

        assert result.paused_until == datetime(2026, 12, 31, 0, 0, 0)


class TestPauseGatesDelivery:
    """Paused prefs suppress the daily digest and instant alerts."""

    @pytest.mark.asyncio
    async def test_daily_report_skipped_when_paused(self):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        mock_report_service = MagicMock()
        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["security"],
                        "channels": ["email"],
                        "min_match_score": None,
                        "is_enabled": True,
                        "paused_until": datetime(2099, 1, 1, 0, 0, 0),
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs._enabled_alert_targets",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "interntrack.scheduler.jobs.ReportService",
                return_value=mock_report_service,
            ),
            patch(
                "interntrack.scheduler.jobs._send_alert_for",
                new=AsyncMock(),
            ),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            await generate_daily_report()

        mock_report_service.generate_daily_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_alert_digest_skipped_when_paused(self):
        """The API digest path also gates on pause (reports.py)."""
        from interntrack.api.v1.reports import _send_alert_digest

        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["email"]
        with (
            patch(
                "interntrack.services.notification_service.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs._deliver_alert",
                new=AsyncMock(return_value={"email": True}),
            ),
            patch(
                "interntrack.scheduler.jobs._record_alert_history",
                new=AsyncMock(),
            ),
        ):
            results = await _send_alert_digest(
                AsyncMock(),
                {
                    "domains": ["security"],
                    "channels": ["email"],
                    "is_enabled": True,
                    "paused_until": datetime(2099, 1, 1, 0, 0, 0),
                },
                {"summary": {}, "new_jobs": []},
            )

        assert results == {}

    @pytest.mark.asyncio
    async def test_instant_alerts_skipped_when_paused(self):
        from interntrack.scheduler.jobs import _send_instant_alerts

        user = MagicMock()
        user.telegram_chat_id = "12345"
        user.location = "Bangalore"
        with patch(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            new=AsyncMock(
                return_value=[
                    {
                        "user_id": "user1",
                        "prefs": {
                            "instant_alerts": True,
                            "domains": ["security"],
                            "min_match_score": None,
                            "paused_until": datetime(2099, 1, 1, 0, 0, 0),
                        },
                        "user": user,
                    }
                ]
            ),
        ):
            sent = await _send_instant_alerts(AsyncMock(), [MagicMock()])

        assert sent == {}


# ---------------------------------------------------------------------------
# Digest preview mode
# ---------------------------------------------------------------------------


class TestDailyReportPreview:
    """GET /reports/daily?preview=1 builds the digest without sending."""

    @pytest.mark.asyncio
    async def test_preview_builds_report_without_sending(self):
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 1, "new_applications": 0},
                "new_jobs": [{"id": "j1", "title": "Security Analyst"}],
            }
        )
        send_mock = AsyncMock(return_value={"email": True})
        mark_sent = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "user1",
                            "prefs": {
                                "domains": ["security"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_alert_digest",
                new=send_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=mark_sent,
            ),
        ):
            report = await get_daily_report(db=mock_db, preview=True)

        # The report is returned...
        assert report["summary"]["new_jobs"] == 1
        assert report["new_jobs"][0]["title"] == "Security Analyst"
        # ...but nothing was sent and the no-duplicates window did NOT move,
        # so previewing never skips a job from the real digest.
        send_mock.assert_not_awaited()
        mark_sent.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_preview_still_sends(self):
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 1, "new_applications": 0},
                "new_jobs": [{"id": "j1", "title": "Security Analyst"}],
            }
        )
        send_mock = AsyncMock(return_value={"email": True})
        mark_sent = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "user1",
                            "prefs": {
                                "domains": ["security"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_alert_digest",
                new=send_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=mark_sent,
            ),
        ):
            report = await get_daily_report(db=mock_db, preview=False)

        assert report["summary"]["new_jobs"] == 1
        send_mock.assert_awaited_once()
        mark_sent.assert_awaited_once()


class TestQuietDayDigest:
    """Days with no new jobs still send a compact confirmation email."""

    @pytest.mark.asyncio
    async def test_quiet_day_emails_instead_of_silence(self):
        """A digest with zero new jobs sends the quiet-day email."""
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 0, "new_applications": 0},
                "new_jobs": [],
            }
        )
        send_mock = AsyncMock()
        quiet_mock = AsyncMock(return_value={"email": True})
        mark_sent = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "user1",
                            "prefs": {
                                "domains": ["security"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_alert_digest",
                new=send_mock,
            ),
            patch(
                "interntrack.api.v1.reports._send_quiet_day_digest",
                new=quiet_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=mark_sent,
            ),
        ):
            report = await get_daily_report(db=mock_db, preview=False)

        assert report["summary"]["new_jobs"] == 0
        # Normal digest skipped (nothing new) but the quiet email went out.
        send_mock.assert_not_awaited()
        quiet_mock.assert_awaited_once()
        mark_sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_afternoon_slot_skips_quiet_day_email(self):
        """Only the morning slot (or manual trigger) sends the quiet email.

        The cron fires 3×/day; without this gate a quiet day would send 3
        'no new jobs' emails. Afternoon/evening slots stay silent instead.
        """
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 0, "new_applications": 0},
                "new_jobs": [],
            }
        )
        quiet_mock = AsyncMock()
        mark_sent = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "user1",
                            "prefs": {
                                "domains": ["security"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_quiet_day_digest",
                new=quiet_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=mark_sent,
            ),
        ):
            await get_daily_report(db=mock_db, preview=False, slot="afternoon")

        quiet_mock.assert_not_awaited()
        mark_sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_morning_slot_sends_quiet_day_email(self):
        """The morning cron slot sends the once-daily quiet email."""
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 0, "new_applications": 0},
                "new_jobs": [],
            }
        )
        quiet_mock = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "user1",
                            "prefs": {
                                "domains": ["security"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_quiet_day_digest",
                new=quiet_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=AsyncMock(),
            ),
        ):
            await get_daily_report(db=mock_db, preview=False, slot="morning")

        quiet_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_preview_never_sends_quiet_day_email(self):
        """Preview mode stays send-free on quiet days too."""
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 0, "new_applications": 0},
                "new_jobs": [],
            }
        )
        quiet_mock = AsyncMock()
        mark_sent = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "user1",
                            "prefs": {
                                "domains": ["security"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_quiet_day_digest",
                new=quiet_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=mark_sent,
            ),
        ):
            await get_daily_report(db=mock_db, preview=True)

        quiet_mock.assert_not_awaited()
        mark_sent.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_quiet_day_skips_when_email_not_enabled(self):
        """Telegram-only accounts don't get the quiet-day email (no spam)."""
        from interntrack.api.v1.reports import _send_quiet_day_digest

        mock_db = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["telegram"]
        mock_manager.notify = AsyncMock(return_value={})

        with (
            patch(
                "interntrack.services.notification_service.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs._record_alert_history",
                new=AsyncMock(),
            ),
        ):
            results = await _send_quiet_day_digest(
                mock_db,
                {"domains": ["security"], "channels": ["telegram"], "is_enabled": True},
                user_id="user1",
            )

        assert results == {}
        mock_manager.notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_quiet_day_never_raises(self):
        """A broken email channel must not break the digest endpoint."""
        from interntrack.api.v1.reports import _send_quiet_day_digest

        mock_db = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["email"]
        mock_manager.notify = AsyncMock(side_effect=RuntimeError("smtp down"))

        with patch(
            "interntrack.services.notification_service.NotificationManager",
            return_value=mock_manager,
        ):
            results = await _send_quiet_day_digest(
                mock_db,
                {"domains": ["security"], "channels": ["email"], "is_enabled": True},
                user_id="user1",
            )

        assert results == {}

    @pytest.mark.asyncio
    async def test_quiet_day_skipped_when_pref_off(self):
        """Accounts with quiet_day_emails off only get real job-alert emails."""
        from interntrack.api.v1.reports import get_daily_report

        mock_db = AsyncMock()
        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "summary": {"new_jobs": 0, "new_applications": 0},
                "new_jobs": [],
            }
        )
        quiet_mock = AsyncMock()
        mark_sent = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports._load_digest_targets",
                new=AsyncMock(
                    return_value=[
                        {
                            "user_id": "friend",
                            "prefs": {
                                "domains": ["frontend"],
                                "channels": ["email"],
                                "min_match_score": None,
                                "is_enabled": True,
                                "quiet_day_emails": False,
                            },
                            "user": None,
                        }
                    ]
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.api.v1.reports._send_quiet_day_digest",
                new=quiet_mock,
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=mark_sent,
            ),
        ):
            await get_daily_report(db=mock_db, preview=False, slot="morning")

        # No new jobs + pref off -> nothing emailed at all.
        quiet_mock.assert_not_awaited()
        mark_sent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_quiet_day_pref_defaults_on(self):
        """quiet_day_emails defaults to True when the row lacks the column."""
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.is_enabled = True
        row.domains = ["security"]
        row.channels = ["email"]
        row.min_match_score = None
        row.last_alert_at = None
        row.slot_domains = None
        row.weekly_enabled = True
        row.instant_alerts = None
        row.include_remote = None
        row.paused_until = None
        # No quiet_day_emails attribute (pre-column rows) -> defaults True.
        del row.quiet_day_emails

        prefs = await _load_alert_preferences(_db_with_row(row))
        assert prefs["quiet_day_emails"] is True

    @pytest.mark.asyncio
    async def test_update_preferences_saves_quiet_day_toggle(self):
        """The PUT endpoint persists quiet_day_emails."""
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        mock_db = _db_with_row(None)
        result = await update_alert_preferences(
            "friend",
            AlertPreferencesUpdate(quiet_day_emails=False),
            db=mock_db,
        )

        assert result.quiet_day_emails is False


# ---------------------------------------------------------------------------
# Weekly top-engaged recap
# ---------------------------------------------------------------------------


class TestTopEngaged:
    """The weekly digest's most-engaged-jobs section."""

    @pytest.mark.asyncio
    async def test_helper_ranks_by_engagement(self):
        from interntrack.api.v1.reports import _top_engaged_jobs

        def _job(jid, title, views=0):
            job = MagicMock()
            job.id = jid
            job.title = title
            job.company = "Acme"
            job.location = "Bangalore"
            job.url = f"https://x/{jid}"
            job.view_count = views
            return job

        jobs = [_job("a", "Hot Role", views=4), _job("b", "Quiet Role")]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = jobs
        mock_db = AsyncMock()

        app_result = MagicMock()
        app_result.all.return_value = [("a", 2)]
        bm_result = MagicMock()
        bm_result.all.return_value = [("a", 1)]

        async def fake_execute(stmt):
            from sqlalchemy import select

            if (
                isinstance(stmt, select)
                and str(getattr(stmt, "column_descriptions", [{}])[0].get("name", ""))
                == "id"
            ):
                return result_mock
            text = str(stmt)
            if "applications" in text and "bookmarks" not in text:
                return app_result
            return bm_result

        mock_db.execute = fake_execute
        # Simpler: just return the job query and empty aggregates.
        mock_db.execute = AsyncMock(side_effect=[result_mock, app_result, bm_result])

        top = await _top_engaged_jobs(mock_db)
        # Job a: 2 apps*3 + 1 bm*2 + 4 views*0.5 = 10.0 ; Job b: 0 -> skipped.
        assert len(top) == 1
        assert top[0]["title"] == "Hot Role"
        assert top[0]["engagement_score"] == 10.0

    @pytest.mark.asyncio
    async def test_helper_never_raises(self):
        from interntrack.api.v1.reports import _top_engaged_jobs

        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("db down")
        assert await _top_engaged_jobs(mock_db) == []

    def test_email_renders_top_engaged(self):
        """The weekly email renders the most-engaged section."""
        from interntrack.scheduler.jobs import build_daily_report_html

        report = {
            "summary": {"new_jobs": 1},
            "new_jobs": [
                {
                    "id": "j1",
                    "title": "Pentester",
                    "company": "Acme",
                    "url": "https://a",
                    "domain": "security",
                    "is_applied": False,
                    "age_days": 0,
                }
            ],
            "top_engaged": [
                {
                    "id": "j1",
                    "title": "Pentester",
                    "company": "Acme",
                    "location": "Bangalore",
                    "url": "https://a",
                    "views": 4,
                    "applications": 2,
                    "bookmarks": 1,
                    "engagement_score": 10.0,
                }
            ],
        }
        with (
            patch(
                "interntrack.scheduler.jobs._score_and_group_jobs",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "interntrack.scheduler.jobs._watched_company_names",
                new=AsyncMock(return_value=set()),
            ),
        ):
            html = _sync_run(build_daily_report_html(report, AsyncMock()))

        assert "🔥 Most engaged this week" in html
        assert "10.0" in html
        assert "2 applied" in html

    def test_telegram_leads_with_top_engaged_on_weekly(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        report = {
            "summary": {"new_jobs": 0},
            "new_jobs": [],
            "top_engaged": [
                {
                    "id": "j1",
                    "title": "Pentester",
                    "company": "Acme",
                    "url": "https://a",
                    "views": 3,
                    "applications": 1,
                    "bookmarks": 0,
                    "engagement_score": 4.5,
                }
            ],
        }
        chunks = _sync_run(build_alert_chunks(report, AsyncMock(), weekly=True))
        first_text = chunks[0][0]
        assert "Most engaged this week" in first_text
        assert "4.5" in first_text

    def test_daily_digest_never_carries_top_engaged(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        report = {
            "summary": {"new_jobs": 1},
            "new_jobs": [
                {
                    "id": "j1",
                    "title": "Security Analyst",
                    "company": "Acme",
                    "url": "https://a",
                    "domain": "security",
                    "is_applied": False,
                    "age_days": 0,
                }
            ],
            "top_engaged": [
                {
                    "id": "j1",
                    "title": "Security Analyst",
                    "company": "Acme",
                    "url": "https://a",
                    "views": 1,
                    "applications": 0,
                    "bookmarks": 0,
                    "engagement_score": 0.5,
                }
            ],
        }
        with (
            patch(
                "interntrack.scheduler.jobs._latest_resume_skill_names",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "interntrack.scheduler.jobs._job_match_score",
                side_effect=[None],
            ),
        ):
            chunks = _sync_run(build_alert_chunks(report, AsyncMock(), weekly=False))

        all_text = "\n".join(t for t, _ in chunks)
        assert "Most engaged this week" not in all_text


def _sync_run(awaitable):
    """Run an async callable inside the running event loop (asyncio_mode=auto)."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    return asyncio.get_event_loop().run_until_complete(awaitable)
