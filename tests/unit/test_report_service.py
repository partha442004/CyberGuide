"""
Unit tests for services/report_service.py.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import jinja2
import pytest

from interntrack.services.report_service import TEMPLATE_DIR, ReportService


class TestReportServiceInit:
    """Tests for ReportService construction and template loading."""

    def test_template_dir_resolves_to_package_templates(self):
        """The template dir points at the package templates (not CWD)."""
        assert TEMPLATE_DIR.name == "templates"
        assert TEMPLATE_DIR.is_dir()

    def test_jinja_env_can_load_all_templates(self):
        """All three report templates exist and load."""
        service = ReportService(MagicMock())
        for report_type in ("daily", "weekly", "monthly"):
            template = service.jinja_env.get_template(f"{report_type}_report.html")
            assert template is not None


class TestRenderReport:
    """Tests for the async HTML rendering path."""

    def setup_method(self):
        self.service = ReportService(MagicMock())

    def _base_data(self, **overrides):
        """Daily report shape with overrides for other report types."""
        data = {
            "report_type": "daily",
            "generated_at": "2026-08-01T00:00:00+00:00",
            "summary": {"new_jobs": 3, "new_applications": 2, "total_applications": 5},
            "new_jobs": [
                {
                    "title": "Python Dev",
                    "company": "Acme",
                    "location": "Remote",
                    "url": "https://x",
                },
            ],
            "closing_soon": [],
            "application_status": {"applied": 5},
        }
        data.update(overrides)
        return data

    @pytest.mark.asyncio
    async def test_renders_daily_template_with_data(self):
        html = await self.service.render_report(self._base_data())
        assert "Daily Report" in html
        assert "Python Dev" in html
        assert "Acme" in html
        assert "3" in html
        assert "applied" in html

    @pytest.mark.asyncio
    async def test_renders_weekly_template_with_data(self):
        data = self._base_data(
            report_type="weekly",
            summary={
                "new_jobs": 3,
                "new_applications": 2,
                "response_rate": 50,
                "rejection_rate": 10,
            },
            top_companies=[{"company": "Acme", "jobs": 4}],
            job_type_distribution=[{"type": "full_time", "count": 2}],
        )
        html = await self.service.render_report(data)
        assert "Weekly Report" in html
        assert "Acme" in html
        assert "full_time" in html
        assert "50%" in html

    @pytest.mark.asyncio
    async def test_renders_monthly_template_with_data(self):
        data = self._base_data(
            report_type="monthly",
            summary={
                "new_jobs": 3,
                "new_applications": 2,
                "response_rate": 50,
                "rejection_rate": 10,
            },
            salary_statistics={"min_salary": 50000, "max_salary": 150000},
            top_companies=[],
            job_type_distribution=[],
        )
        html = await self.service.render_report(data)
        assert "Monthly Report" in html
        # Template formats salaries with "{:,.0f}", so 50000 renders as 50,000
        assert "50,000" in html
        assert "150,000" in html

    @pytest.mark.asyncio
    async def test_unknown_report_type_raises(self):
        """An unknown report type has no template and raises TemplateNotFound."""
        with pytest.raises(jinja2.TemplateNotFound):
            await self.service.render_report(
                {"report_type": "unknown", "summary": {}},
            )

    @pytest.mark.asyncio
    async def test_autoescape_escapes_html(self):
        """Template autoescape prevents HTML injection in job titles."""
        data = self._base_data(
            generated_at="",
            summary={"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            new_jobs=[
                {
                    "title": "<script>alert(1)</script>",
                    "company": "Acme",
                    "location": None,
                    "url": None,
                },
            ],
        )
        html = await self.service.render_report(data)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class _MockJob:
    """Minimal job stand-in for repo results."""

    def __init__(
        self,
        title="Job",
        company="Acme",
        location="Remote",
        url="https://x",
        expires_at=None,
        created_at=None,
        posted_at=None,
        is_active=True,
    ):
        self.title = title
        self.company = company
        self.location = location
        self.url = url
        self.expires_at = expires_at
        self.created_at = created_at
        self.posted_at = posted_at
        self.is_active = is_active


class TestGenerateDailyReport:
    """Tests for generate_daily_report with mocked repositories."""

    @pytest.mark.asyncio
    async def test_returns_expected_shape(self):
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [_MockJob()]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = [object()]
        service.app_repo.get_status_counts.return_value = {"applied": 5}
        service.job_repo.get_closing_soon.return_value = [
            _MockJob(title="Closing", expires_at=datetime.now(UTC)),
        ]

        report = await service.generate_daily_report()

        assert report["report_type"] == "daily"
        assert report["summary"] == {
            "new_jobs": 1,
            "new_applications": 1,
            "total_applications": 5,
        }
        assert report["new_jobs"][0]["title"] == "Job"
        assert report["closing_soon"][0]["title"] == "Closing"
        assert report["application_status"] == {"applied": 5}

    @pytest.mark.asyncio
    async def test_jobs_carry_age_and_expiry_fields(self):
        """Each new_jobs entry exposes age_days, expiry and activity flags."""
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        from datetime import timedelta

        now = datetime.now(UTC).replace(tzinfo=None)
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(
                title="Old Job",
                posted_at=now - timedelta(days=2),
                expires_at=now + timedelta(days=1),
                is_active=True,
            ),
            _MockJob(
                title="Closed Job",
                posted_at=now,
                expires_at=now - timedelta(days=1),
                is_active=False,
            ),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report()

        old, closed = report["new_jobs"]
        assert old["age_days"] == 2
        assert old["is_active"] is True
        assert old["expires_at"] is not None
        assert old["posted_at"] is not None
        assert closed["age_days"] == 0
        assert closed["is_active"] is False


class TestGenerateWeeklyReport:
    """Tests for generate_weekly_report with mocked repositories."""

    @pytest.mark.asyncio
    async def test_returns_expected_shape(self):
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [_MockJob()]
        service.job_repo.get_top_companies.return_value = [("Acme", 4)]
        service.job_repo.get_job_type_distribution.return_value = []
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = [object()]
        service.app_repo.get_status_counts.return_value = {"applied": 5}
        service.app_repo.get_rejection_rate.return_value = 10.0
        service.app_repo.get_response_rate.return_value = 50.0
        service.app_repo.get_application_timeline.return_value = []

        report = await service.generate_weekly_report()

        assert report["report_type"] == "weekly"
        assert report["top_companies"] == [{"company": "Acme", "jobs": 4}]
        assert report["summary"]["response_rate"] == 50.0
        assert report["summary"]["rejection_rate"] == 10.0


class TestGenerateMonthlyReport:
    """Tests for generate_monthly_report with mocked repositories."""

    @pytest.mark.asyncio
    async def test_builds_on_weekly_and_adds_salary(self):
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = []
        service.job_repo.get_top_companies.return_value = []
        service.job_repo.get_job_type_distribution.return_value = []
        service.job_repo.get_salary_statistics.return_value = {
            "min_salary": 50000,
            "max_salary": 150000,
        }
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_rejection_rate.return_value = 0.0
        service.app_repo.get_response_rate.return_value = 0.0
        service.app_repo.get_application_timeline.return_value = []

        report = await service.generate_monthly_report()

        assert report["report_type"] == "monthly"
        assert report["salary_statistics"] == {
            "min_salary": 50000,
            "max_salary": 150000,
        }
        assert report["monthly_applications"] == []
