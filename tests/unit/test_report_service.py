"""Unit tests for services/report_service.py."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestReportService:
    """Tests for ReportService class."""

    def test_init(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)
        assert service.session == session
        assert service.job_repo is not None
        assert service.app_repo is not None

    @pytest.mark.asyncio
    async def test_generate_daily_report(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        mock_job = MagicMock()
        mock_job.title = "Security Analyst"
        mock_job.company = "Tech Corp"
        mock_job.location = "Remote"
        mock_job.url = "https://example.com"
        mock_job.expires_at = None

        service.job_repo.get_recent_jobs = AsyncMock(return_value=[mock_job])
        service.job_repo.get_closing_soon = AsyncMock(return_value=[])
        service.app_repo.get_recent_applications = AsyncMock(return_value=[])
        service.app_repo.get_status_counts = AsyncMock(return_value={"applied": 5})

        result = await service.generate_daily_report()

        assert result["report_type"] == "daily"
        assert "generated_at" in result
        assert result["summary"]["new_jobs"] == 1
        assert result["summary"]["new_applications"] == 0
        assert len(result["new_jobs"]) == 1
        assert result["new_jobs"][0]["title"] == "Security Analyst"

    @pytest.mark.asyncio
    async def test_generate_daily_report_with_closing_soon(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        mock_closing = MagicMock()
        mock_closing.title = "SOC Analyst"
        mock_closing.company = "Security Inc"
        mock_closing.expires_at = datetime(2026, 8, 15, tzinfo=timezone.utc)

        service.job_repo.get_recent_jobs = AsyncMock(return_value=[])
        service.job_repo.get_closing_soon = AsyncMock(return_value=[mock_closing])
        service.app_repo.get_recent_applications = AsyncMock(return_value=[])
        service.app_repo.get_status_counts = AsyncMock(return_value={})

        result = await service.generate_daily_report()

        assert result["report_type"] == "daily"
        assert len(result["closing_soon"]) == 1
        assert result["closing_soon"][0]["title"] == "SOC Analyst"
        assert result["closing_soon"][0]["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_generate_weekly_report(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        mock_job = MagicMock()
        mock_job.title = "SOC Analyst"
        mock_job.company = "Security Inc"

        service.job_repo.get_recent_jobs = AsyncMock(return_value=[mock_job])
        service.job_repo.get_top_companies = AsyncMock(return_value=[("Tech Corp", 5)])
        service.job_repo.get_job_type_distribution = AsyncMock(return_value=[])
        service.app_repo.get_recent_applications = AsyncMock(return_value=[])
        service.app_repo.get_status_counts = AsyncMock(return_value={"applied": 3})
        service.app_repo.get_rejection_rate = AsyncMock(return_value=0.1)
        service.app_repo.get_response_rate = AsyncMock(return_value=0.3)
        service.app_repo.get_application_timeline = AsyncMock(return_value=[])

        result = await service.generate_weekly_report()

        assert result["report_type"] == "weekly"
        assert result["summary"]["new_jobs"] == 1
        assert result["summary"]["rejection_rate"] == 0.1
        assert result["summary"]["response_rate"] == 0.3
        assert len(result["top_companies"]) == 1

    @pytest.mark.asyncio
    async def test_generate_weekly_report_with_job_types(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        mock_jtype = MagicMock()
        mock_jtype.value = "full_time"

        service.job_repo.get_recent_jobs = AsyncMock(return_value=[])
        service.job_repo.get_top_companies = AsyncMock(return_value=[])
        service.job_repo.get_job_type_distribution = AsyncMock(return_value=[(mock_jtype, 15)])
        service.app_repo.get_recent_applications = AsyncMock(return_value=[])
        service.app_repo.get_status_counts = AsyncMock(return_value={})
        service.app_repo.get_rejection_rate = AsyncMock(return_value=0.0)
        service.app_repo.get_response_rate = AsyncMock(return_value=0.0)
        service.app_repo.get_application_timeline = AsyncMock(return_value=[])

        result = await service.generate_weekly_report()

        assert result["report_type"] == "weekly"
        assert len(result["job_type_distribution"]) == 1
        assert result["job_type_distribution"][0]["type"] == "full_time"
        assert result["job_type_distribution"][0]["count"] == 15

    @pytest.mark.asyncio
    async def test_generate_monthly_report(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        service.job_repo.get_recent_jobs = AsyncMock(return_value=[])
        service.job_repo.get_top_companies = AsyncMock(return_value=[])
        service.job_repo.get_job_type_distribution = AsyncMock(return_value=[])
        service.job_repo.get_salary_statistics = AsyncMock(return_value={"avg_min": 50000})
        service.app_repo.get_recent_applications = AsyncMock(return_value=[])
        service.app_repo.get_status_counts = AsyncMock(return_value={})
        service.app_repo.get_rejection_rate = AsyncMock(return_value=0.0)
        service.app_repo.get_response_rate = AsyncMock(return_value=0.0)
        service.app_repo.get_application_timeline = AsyncMock(return_value=[])

        result = await service.generate_monthly_report()

        assert result["report_type"] == "monthly"
        assert "salary_statistics" in result
        assert result["salary_statistics"]["avg_min"] == 50000

    @pytest.mark.asyncio
    async def test_generate_monthly_report_with_salary_stats(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        service.job_repo.get_recent_jobs = AsyncMock(return_value=[])
        service.job_repo.get_top_companies = AsyncMock(return_value=[])
        service.job_repo.get_job_type_distribution = AsyncMock(return_value=[])
        service.job_repo.get_salary_statistics = AsyncMock(return_value={
            "avg_min": 60000,
            "avg_max": 120000,
            "median": 90000,
        })
        service.app_repo.get_recent_applications = AsyncMock(return_value=[])
        service.app_repo.get_status_counts = AsyncMock(return_value={})
        service.app_repo.get_rejection_rate = AsyncMock(return_value=0.0)
        service.app_repo.get_response_rate = AsyncMock(return_value=0.0)
        service.app_repo.get_application_timeline = AsyncMock(return_value=[])

        result = await service.generate_monthly_report()

        assert result["report_type"] == "monthly"
        assert result["salary_statistics"]["avg_min"] == 60000
        assert result["salary_statistics"]["avg_max"] == 120000
        assert result["salary_statistics"]["median"] == 90000
