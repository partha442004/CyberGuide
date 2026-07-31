"""Unit tests for scheduler/jobs.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestFormatDailyReport:
    """Tests for format_daily_report function."""

    def test_format_daily_report_basic(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {
            "summary": {
                "new_jobs": 5,
                "new_applications": 3,
                "total_applications": 10,
            }
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


@pytest.mark.asyncio
class TestRunJobDiscovery:
    """Tests for run_job_discovery async function."""

    @patch("interntrack.scrapers.registry.get_default_registry")
    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_run_job_discovery_success(self, mock_get_db, mock_service_cls, mock_registry_fn):
        from interntrack.scheduler.jobs import run_job_discovery

        # Setup mocks
        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_registry = AsyncMock()
        mock_registry.fetch_all.return_value = [{"title": "Python Dev", "company": "TechCo"}]
        mock_registry_fn.return_value = mock_registry

        mock_service = AsyncMock()
        mock_service.save_jobs.return_value = [{"title": "Python Dev"}]
        mock_service_cls.return_value = mock_service

        # Run
        await run_job_discovery()

        # Verify
        mock_registry.fetch_all.assert_called_once()
        mock_service.save_jobs.assert_called_once_with(
            [{"title": "Python Dev", "company": "TechCo"}]
        )

    @patch("interntrack.scrapers.registry.get_default_registry")
    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_run_job_discovery_no_jobs(self, mock_get_db, mock_service_cls, mock_registry_fn):
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
        self, mock_get_db, mock_report_cls, mock_notif_cls
    ):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_report_service = AsyncMock()
        mock_report_service.generate_daily_report.return_value = {
            "summary": {"new_jobs": 5, "new_applications": 3, "total_applications": 10}
        }
        mock_report_cls.return_value = mock_report_service

        mock_manager = AsyncMock()
        mock_manager.notify_all.return_value = True
        mock_notif_cls.return_value = mock_manager

        await generate_daily_report()

        mock_report_service.generate_daily_report.assert_called_once()
        mock_manager.notify_all.assert_called_once()

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
