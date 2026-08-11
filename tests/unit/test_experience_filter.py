"""Unit tests for per-user experience-level filtering of job alerts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestJobExperienceOk:
    def test_empty_or_missing_list_passes_everything(self):
        from interntrack.utils.helpers import job_experience_ok

        job = SimpleNamespace(experience_level="senior")
        assert job_experience_ok(job, None) is True
        assert job_experience_ok(job, []) is True

    def test_entry_only_drops_senior_roles(self):
        from interntrack.utils.helpers import job_experience_ok

        entry_ok = SimpleNamespace(experience_level="entry")
        senior = SimpleNamespace(experience_level="senior")
        assert job_experience_ok(entry_ok, ["entry"]) is True
        assert job_experience_ok(senior, ["entry"]) is False

    def test_fresher_mode_keeps_unspecified_listings(self):
        from interntrack.utils.helpers import job_experience_ok

        # No parsed level / unknown / fresher / intern tags always pass:
        # an unspecified posting may still be fresher-friendly.
        for level in (None, "", "unknown", "fresher", "intern"):
            job = SimpleNamespace(experience_level=level)
            assert job_experience_ok(job, ["entry", "junior"]) is True, level

    def test_fresher_mode_keeps_entry_and_junior(self):
        from interntrack.utils.helpers import job_experience_ok

        assert (
            job_experience_ok(
                SimpleNamespace(experience_level="entry"), ["entry", "junior"]
            )
            is True
        )
        assert (
            job_experience_ok(
                SimpleNamespace(experience_level="junior"), ["entry", "junior"]
            )
            is True
        )

    def test_fresher_mode_drops_mid_senior_lead_executive(self):
        from interntrack.utils.helpers import job_experience_ok

        for level in ("mid", "senior", "lead", "executive"):
            job = SimpleNamespace(experience_level=level)
            assert job_experience_ok(job, ["entry", "junior"]) is False, level

    def test_levels_compared_case_insensitively(self):
        from interntrack.utils.helpers import job_experience_ok

        assert (
            job_experience_ok(SimpleNamespace(experience_level="SENIOR"), ["senior"])
            is True
        )

    def test_works_with_plain_dicts(self):
        from interntrack.utils.helpers import job_experience_ok

        # The closing-soon sweep filters dict rows, not ORM objects.
        assert job_experience_ok({"experience_level": "senior"}, ["entry"]) is False
        assert job_experience_ok({"experience_level": "entry"}, ["entry"]) is True
        assert job_experience_ok({}, ["entry"]) is True

    def test_bad_input_never_raises(self):
        from interntrack.utils.helpers import job_experience_ok

        assert job_experience_ok(None, ["entry"]) is True
        # Garbage level values never raise; they just fail the set check.
        assert (
            job_experience_ok(SimpleNamespace(experience_level=123), ["entry"]) is False
        )
        # A non-list allowed value never raises either (falls through safe).
        assert job_experience_ok(SimpleNamespace(experience_level="senior"), 42) is True


def _db_with_row(row) -> AsyncMock:
    """Session mock whose execute() returns a result exposing the row."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result)
    return mock_db


class TestLoadAlertPreferences:
    @pytest.mark.asyncio
    async def test_returns_saved_experience_levels(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.domains = ["security"]
        row.channels = ["email"]
        row.is_enabled = True
        row.experience_levels = ["entry", "junior"]

        prefs = await _load_alert_preferences(_db_with_row(row), user_id="user1")
        assert prefs.get("experience_levels") == ["entry", "junior"]

    @pytest.mark.asyncio
    async def test_missing_column_defaults_to_empty(self):
        from interntrack.scheduler.jobs import _load_alert_preferences

        row = MagicMock()
        row.domains = ["security"]
        row.channels = ["email"]
        row.is_enabled = True
        row.experience_levels = None

        prefs = await _load_alert_preferences(_db_with_row(row), user_id="user1")
        assert prefs.get("experience_levels") == []


class TestReportFiltersByExperience:
    @pytest.mark.asyncio
    async def test_senior_jobs_dropped_in_fresher_mode(self):
        from interntrack.services.report_service import ReportService

        def _job(level):
            return SimpleNamespace(
                id="j1",
                title="Security Analyst",
                company="Acme",
                location="Bangalore",
                url="https://example.com",
                description="",
                tags=[],
                required_skills=[],
                preferred_skills=[],
                posted_at=None,
                created_at=None,
                expires_at=None,
                is_active=True,
                salary_min=None,
                salary_max=None,
                salary_currency=None,
                experience_level=level,
            )

        service = ReportService.__new__(ReportService)
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [
            _job("entry"),
            _job("junior"),
            _job("senior"),
            _job("mid"),
            _job(None),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_top_companies.return_value = []

        report = await service.generate_daily_report(
            domains=["security"],
            experience_levels=["entry", "junior"],
        )
        titles = [job["title"] for job in report["new_jobs"]]
        assert titles == ["Security Analyst"] * 3  # entry, junior + unparsed

    @pytest.mark.asyncio
    async def test_all_levels_when_no_filter(self):
        from interntrack.services.report_service import ReportService

        def _job(level):
            return SimpleNamespace(
                id="j1",
                title="Security Analyst",
                company="Acme",
                location="Bangalore",
                url="https://example.com",
                description="",
                tags=[],
                required_skills=[],
                preferred_skills=[],
                posted_at=None,
                created_at=None,
                expires_at=None,
                is_active=True,
                salary_min=None,
                salary_max=None,
                salary_currency=None,
                experience_level=level,
            )

        service = ReportService.__new__(ReportService)
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [_job("entry"), _job("senior")]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_top_companies.return_value = []

        report = await service.generate_daily_report(domains=["security"])
        assert len(report["new_jobs"]) == 2


class TestApiPrefsExperienceLevels:
    @pytest.mark.asyncio
    async def test_put_saves_and_get_returns_experience_levels(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        row = MagicMock()
        row.user_id = "user1"
        row.experience_levels = None
        row.domains = None
        row.channels = None
        row.min_match_score = None
        row.is_enabled = True
        row.last_alert_at = None
        row.slot_domains = None
        row.weekly_enabled = None
        row.instant_alerts = None
        row.include_remote = None
        row.quiet_day_emails = None
        row.paused_until = None
        row.min_salary = None
        row.keywords = None

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=row)
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        update = AlertPreferencesUpdate(experience_levels=["entry", "junior"])
        resp = await update_alert_preferences("user1", update, session)
        assert resp.experience_levels == ["entry", "junior"]
        assert row.experience_levels == ["entry", "junior"]

    @pytest.mark.asyncio
    async def test_put_empty_list_clears_the_filter(self):
        from interntrack.api.schemas.notification import AlertPreferencesUpdate
        from interntrack.api.v1.notifications import update_alert_preferences

        # A saved fresher filter that the dashboard must be able to clear:
        # "All levels" maps to [] (NOT None, which means "keep current").
        row = MagicMock()
        row.user_id = "user1"
        row.experience_levels = ["entry", "junior"]
        row.domains = None
        row.channels = None
        row.min_match_score = None
        row.is_enabled = True
        row.last_alert_at = None
        row.slot_domains = None
        row.weekly_enabled = None
        row.instant_alerts = None
        row.include_remote = None
        row.quiet_day_emails = None
        row.paused_until = None
        row.min_salary = None
        row.keywords = None

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=row)
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        update = AlertPreferencesUpdate(experience_levels=[])
        resp = await update_alert_preferences("user1", update, session)
        assert resp.experience_levels == []
        assert row.experience_levels == []
