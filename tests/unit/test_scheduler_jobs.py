"""Unit tests for scheduler/jobs.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFormatDailyReport:
    """Tests for format_daily_report function."""

    def test_format_daily_report_basic(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {
            "summary": {
                "new_jobs": 5,
                "new_applications": 3,
                "total_applications": 10,
            },
        }

        result = format_daily_report(report)

        assert "📊 Daily Report" in result
        assert "New Jobs: 5" in result
        assert "New Applications: 3" in result
        assert "Total Applications: 10" in result

    def test_format_daily_report_empty(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {}
        result = format_daily_report(report)

        assert "📊 Daily Report" in result
        assert "New Jobs: 0" in result
        assert "New Applications: 0" in result
        assert "Total Applications: 0" in result

    def test_format_daily_report_missing_summary(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {"other_key": "value"}
        result = format_daily_report(report)

        assert "New Jobs: 0" in result

    def test_format_daily_report_partial_summary(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {"summary": {"new_jobs": 10}}
        result = format_daily_report(report)

        assert "New Jobs: 10" in result
        assert "New Applications: 0" in result
        assert "Total Applications: 0" in result


class TestBuildDailyReportMessage:
    """Tests for the rich daily-report message (links + match %)."""

    @pytest.mark.asyncio
    async def test_includes_job_links_and_match_percent(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security", "python"],
                }
            ],
        }

        class FakeResume:
            skills = [{"name": "Python", "category": "scripting"}]

        class FakeResult:
            def scalar_one_or_none(self):
                return FakeResume()

        class FakeSession:
            async def execute(self, *args, **kwargs):
                return FakeResult()

        message = await build_daily_report_message(report, FakeSession())

        assert "Security Engineer" in message
        assert "Acme Corp" in message
        assert "Apply" in message
        assert "https://acme.example/apply" in message
        assert "%" in message

    @pytest.mark.asyncio
    async def test_no_jobs_keeps_summary_only(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {"summary": {"new_jobs": 0, "new_applications": 0}}
        message = await build_daily_report_message(report, None)
        assert "New Jobs: 0" in message
        assert "Apply" not in message

    @pytest.mark.asyncio
    async def test_groups_jobs_by_domain_sections(self):
        """Jobs are grouped into domain sections with age badges."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 3, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "title": "SOC Analyst",
                    "company": "SecureCo",
                    "url": "https://a/apply",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": True,
                },
                {
                    "title": "Python Developer",
                    "company": "TechCo",
                    "url": "https://b/apply",
                    "age_days": 1,
                    "domain": "coding",
                    "is_applied": False,
                },
                {
                    "title": "Old Job",
                    "company": "C",
                    "url": "https://c/apply",
                    "age_days": 5,
                    "domain": "security",
                    "is_applied": False,
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "Cybersecurity / VAPT / SOC (2)" in message
        assert "Coding / Software (1)" in message
        assert "SOC Analyst" in message
        assert "Python Developer" in message
        assert "✅ Applied" in message
        assert "⬜ Not applied" in message
        assert "🟢 today" in message
        assert "🟡 1d ago" in message
        assert "⚪ 5d ago" in message

    @pytest.mark.asyncio
    async def test_expiry_badges_in_message(self):
        """Closing-soon and expired jobs get visible badges."""
        from datetime import UTC, datetime, timedelta

        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 2, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "title": "Closing Job",
                    "company": "A",
                    "url": "https://a/apply",
                    "age_days": 0,
                    "is_active": True,
                    "expires_at": ((datetime.now(UTC) + timedelta(days=1)).isoformat()),
                },
                {
                    "title": "Dead Job",
                    "company": "B",
                    "url": "https://b/apply",
                    "age_days": 0,
                    "is_active": False,
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "Closing soon" in message
        assert "Expired / closed" in message

    def test_expiry_note(self):
        from datetime import UTC, datetime, timedelta

        from interntrack.scheduler.jobs import _expiry_note

        assert _expiry_note({"is_active": False}) == "   ❌ Expired / closed"
        assert _expiry_note({"is_active": True}) == ""
        assert "Closing soon" in _expiry_note(
            {
                "is_active": True,
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        )
        assert "Expired" in _expiry_note(
            {
                "is_active": True,
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )

    @pytest.mark.asyncio
    async def test_closing_soon_section_in_message(self):
        """Deadline jobs lead the daily digest so they aren't missed."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [],
            "closing_soon": [
                {
                    "title": "VAPT Intern",
                    "company": "SecureCo",
                    "expires_at": "2026-08-09T00:00:00",
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "🚨 Closing soon (1):" in message
        assert "VAPT Intern" in message
        assert "SecureCo" in message

    def test_age_badge(self):
        from interntrack.scheduler.jobs import _age_badge

        assert _age_badge(0) == "🟢 today"
        assert _age_badge(1) == "🟡 1d ago"
        assert _age_badge(2) == "🟠 2d ago"
        assert _age_badge(7) == "⚪ 7d ago"


@pytest.mark.asyncio
class TestRunJobDiscovery:
    """Tests for run_job_discovery async function."""

    @patch("interntrack.scrapers.registry.get_default_registry")
    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_run_job_discovery_success(
        self,
        mock_get_db,
        mock_service_cls,
        mock_registry_fn,
    ):
        from interntrack.scheduler.jobs import run_job_discovery

        # Setup mocks
        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_registry = AsyncMock()
        mock_registry.fetch_all.return_value = [
            {"title": "Python Dev", "company": "TechCo"},
        ]
        mock_registry_fn.return_value = mock_registry

        mock_service = AsyncMock()
        mock_service.save_jobs.return_value = [{"title": "Python Dev"}]
        mock_service_cls.return_value = mock_service

        # Run
        await run_job_discovery()

        # Verify
        mock_registry.fetch_all.assert_called_once()
        mock_service.save_jobs.assert_called_once_with(
            [{"title": "Python Dev", "company": "TechCo"}],
        )

    @patch("interntrack.scrapers.registry.get_default_registry")
    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_run_job_discovery_no_jobs(
        self,
        mock_get_db,
        mock_service_cls,
        mock_registry_fn,
    ):
        from interntrack.scheduler.jobs import run_job_discovery

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_registry = AsyncMock()
        mock_registry.fetch_all.return_value = []
        mock_registry_fn.return_value = mock_registry

        mock_service = AsyncMock()
        mock_service.save_jobs.return_value = []
        mock_service_cls.return_value = mock_service

        await run_job_discovery()

        mock_registry.fetch_all.assert_called_once()
        mock_service.save_jobs.assert_called_with([])

    """Tests for generate_daily_report async function."""


class TestGenerateDailyReport:
    """Tests for generate_daily_report async function."""

    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch("interntrack.scheduler.jobs.ReportService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    @pytest.mark.asyncio
    async def test_generate_daily_report_success(
        self,
        mock_get_db,
        mock_report_cls,
        mock_notif_cls,
    ):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_report_service = AsyncMock()
        mock_report_service.generate_daily_report.return_value = {
            "summary": {"new_jobs": 5, "new_applications": 3, "total_applications": 10},
            "new_jobs": [{}],
        }
        mock_report_cls.return_value = mock_report_service

        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["telegram"]
        mock_manager.notify = AsyncMock(return_value={"telegram": True})
        mock_notif_cls.return_value = mock_manager

        with (
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": [],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": True,
                        "last_alert_at": None,
                        "slot_domains": {},
                        "weekly_enabled": True,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk", [("Apply", "https://x")])]),
            ),
        ):
            await generate_daily_report()

        mock_report_service.generate_daily_report.assert_called_once()
        mock_manager.notify.assert_awaited_once_with(
            ["telegram"],
            "chunk",
            subject="Daily Report",
            buttons=[("Apply", "https://x")],
        )

    @patch("interntrack.engines.verification.VerificationEngine")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_verify_job_links(self, mock_get_db, mock_engine_cls):
        from interntrack.scheduler.jobs import verify_job_links

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_engine = AsyncMock()
        mock_engine.verify_all_links.return_value = [
            {"url": "http://alive.com", "is_alive": True},
            {"url": "http://dead.com", "is_alive": False},
        ]
        mock_engine_cls.return_value = mock_engine

        await verify_job_links()

        mock_engine.verify_all_links.assert_called_once()

    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    @pytest.mark.asyncio
    async def test_deactivate_expired_jobs(self, mock_get_db, mock_service_cls):
        from interntrack.scheduler.jobs import deactivate_expired_jobs

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_service = AsyncMock()
        mock_service.deactivate_expired.return_value = 3
        mock_service_cls.return_value = mock_service

        await deactivate_expired_jobs()

        mock_service.deactivate_expired.assert_called_once()

    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    @pytest.mark.asyncio
    async def test_deactivate_expired_jobs_none(self, mock_get_db, mock_service_cls):
        from interntrack.scheduler.jobs import deactivate_expired_jobs

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_service = AsyncMock()
        mock_service.deactivate_expired.return_value = 0
        mock_service_cls.return_value = mock_service

        await deactivate_expired_jobs()

        mock_service.deactivate_expired.assert_called_once()
