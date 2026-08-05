"""
Tests for daily-alert preferences: the model-backed preference loader,
preferences API endpoints (get / upsert / send-alert), domain filtering in
the report service, and match-threshold filtering in the alert message.
"""

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

        prefs = await _load_alert_preferences(_db_with_row(row))
        assert prefs == {
            "domains": ["security"],
            "channels": [],
            "min_match_score": None,
            "is_enabled": False,
        }

    @pytest.mark.asyncio
    async def test_enabled_row_returns_prefs(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.is_enabled = True
        row.domains = ["security"]
        row.channels = ["email"]
        row.min_match_score = 60

        prefs = await _load_alert_preferences(_db_with_row(row))
        assert prefs == {
            "domains": ["security"],
            "channels": ["email"],
            "min_match_score": 60,
            "is_enabled": True,
        }

    @pytest.mark.asyncio
    async def test_loads_prefs_for_given_user(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.is_enabled = True
        row.domains = ["coding"]
        row.channels = []
        row.min_match_score = None

        prefs = await _load_alert_preferences(_db_with_row(row), user_id="user2")
        assert prefs["domains"] == ["coding"]

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
                "interntrack.scheduler.jobs.build_daily_report_message",
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
        mock_manager.notify_all = AsyncMock(return_value={"telegram": True})

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
        ):
            result = await send_alert_now("user1", db=mock_db)

        assert result["results"] == {"telegram": True}
        assert result["domains"] == []
        mock_manager.notify_all.assert_awaited_once()
        mock_manager.notify.assert_not_called()

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
        )
        mock_manager.notify.assert_awaited_once_with(
            ["telegram"], "msg", subject="InternTrack Daily Alert (coding)"
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


# ---------------------------------------------------------------------------
# Report service domain filtering
# ---------------------------------------------------------------------------


class _MockJob:
    """Minimal job stand-in matching the repo contract."""

    def __init__(self, title="Job", company="Acme", job_id="j1"):
        self.title = title
        self.company = company
        self.location = "Remote"
        self.url = "https://x"
        self.expires_at = None
        self.created_at = None
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
