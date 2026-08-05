"""Unit tests for scheduler/jobs.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFormatDailyReport:
    """Tests for format_daily_report function."""

    def test_format_daily_report_basic(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {
            "summary": {
                "new_jobs": 15,
                "new_applications": 3,
                "total_applications": 25,
            },
        }

        result = format_daily_report(report)

        assert "📊 Daily Report" in result
        assert "New Jobs: 15" in result
        assert "New Applications: 3" in result
        assert "Total Applications: 25" in result

    def test_format_daily_report_empty(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {}

        result = format_daily_report(report)

        assert "📊 Daily Report" in result
        assert "New Jobs: 0" in result

    def test_format_daily_report_partial(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {"summary": {"new_jobs": 5}}

        result = format_daily_report(report)

        assert "New Jobs: 5" in result
        assert "New Applications: 0" in result


class TestRunJobDiscovery:
    """Tests for run_job_discovery function."""

    @pytest.mark.asyncio
    async def test_run_job_discovery(self):
        from interntrack.scheduler.jobs import run_job_discovery

        mock_session = AsyncMock()
        mock_service = MagicMock()
        mock_service.save_jobs = AsyncMock(return_value=[MagicMock(), MagicMock()])

        mock_registry = MagicMock()
        mock_registry.fetch_all = AsyncMock(
            return_value=[MagicMock(), MagicMock(), MagicMock()],
        )

        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch("interntrack.scheduler.jobs.JobService", return_value=mock_service),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "interntrack.scrapers.registry.get_default_registry",
                return_value=mock_registry,
            ):
                await run_job_discovery()

            mock_registry.fetch_all.assert_called_once()


class TestGenerateDailyReport:
    """Tests for generate_daily_report function."""

    @pytest.mark.asyncio
    async def test_generate_daily_report(self):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()

        mock_report_service = MagicMock()
        mock_report_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "summary": {
                    "new_jobs": 5,
                    "new_applications": 2,
                    "total_applications": 10,
                },
                "new_jobs": [{}],
            },
        )

        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["telegram"]
        mock_manager.notify = AsyncMock(return_value={"telegram": True})
        mock_manager.notify_all = AsyncMock(return_value={"telegram": True})

        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch(
                "interntrack.scheduler.jobs.ReportService",
                return_value=mock_report_service,
            ),
            patch(
                "interntrack.scheduler.jobs.NotificationManager",
                return_value=mock_manager,
            ),
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
                new=AsyncMock(return_value=[("chunk", [])]),
            ),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            await generate_daily_report()

            mock_report_service.generate_daily_report.assert_called_once()
            mock_manager.notify.assert_awaited_once_with(
                ["telegram"],
                "chunk",
                subject="Daily Report",
                buttons=[],
            )


class TestVerifyJobLinks:
    """Tests for verify_job_links function."""

    @pytest.mark.asyncio
    async def test_verify_job_links(self):
        from interntrack.scheduler.jobs import verify_job_links

        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.verify_all_links = AsyncMock(
            return_value=[
                {"url": "https://example.com/1", "is_alive": True},
                {"url": "https://example.com/2", "is_alive": False},
            ],
        )

        with patch("interntrack.scheduler.jobs.get_db_session") as mock_db:
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "interntrack.engines.verification.VerificationEngine",
                return_value=mock_engine,
            ):
                await verify_job_links()

                mock_engine.verify_all_links.assert_called_once()


class TestDeactivateExpiredJobs:
    """Tests for deactivate_expired_jobs function."""

    @pytest.mark.asyncio
    async def test_deactivate_expired_jobs(self):
        from interntrack.scheduler.jobs import deactivate_expired_jobs

        mock_session = AsyncMock()
        mock_service = MagicMock()
        mock_service.deactivate_expired = AsyncMock(return_value=5)

        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch("interntrack.scheduler.jobs.JobService", return_value=mock_service),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            await deactivate_expired_jobs()

            mock_service.deactivate_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_expired_jobs_none(self):
        from interntrack.scheduler.jobs import deactivate_expired_jobs

        mock_session = AsyncMock()
        mock_service = MagicMock()
        mock_service.deactivate_expired = AsyncMock(return_value=0)

        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch("interntrack.scheduler.jobs.JobService", return_value=mock_service),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            await deactivate_expired_jobs()

            mock_service.deactivate_expired.assert_called_once()
