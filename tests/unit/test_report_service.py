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
        description=None,
        expires_at=None,
        created_at=None,
        posted_at=None,
        is_active=True,
        job_id="j1",
        tags=None,
    ):
        self.title = title
        self.company = company
        self.location = location
        self.url = url
        self.description = description
        self.expires_at = expires_at
        self.created_at = created_at
        self.posted_at = posted_at
        self.is_active = is_active
        self.id = job_id
        self.tags = tags


class TestGenerateDailyReport:
    """Tests for generate_daily_report with mocked repositories."""

    @pytest.mark.asyncio
    async def test_returns_expected_shape(self):
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [_MockJob(job_id="j1")]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = [object()]
        service.app_repo.get_status_counts.return_value = {"applied": 5}
        service.app_repo.get_applied_job_ids.return_value = {"j1"}
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
        assert report["new_jobs"][0]["is_applied"] is True
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
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report()

        old, closed = report["new_jobs"]
        assert old["age_days"] == 2
        assert old["is_active"] is True
        assert old["expires_at"] is not None
        assert old["posted_at"] is not None
        assert closed["age_days"] == 0
        assert closed["is_active"] is False

    @pytest.mark.asyncio
    async def test_jobs_carry_description_field(self):
        """Each new_jobs entry exposes the posting's description so digests
        can render what the role expects (responsibilities / requirements)."""
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(
                title="SOC Analyst",
                description="Monitor SIEM alerts, triage incidents, ...",
            ),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report()

        assert report["new_jobs"][0]["description"] == (
            "Monitor SIEM alerts, triage incidents, ..."
        )

    @pytest.mark.asyncio
    async def test_location_filter_keeps_only_user_city(self):
        """A digest location keeps only that city, synonym-aware, plus remote
        when the user opted into remote work (include_remote default True)."""
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(
                title="Frontend Dev",
                location="Bengaluru, Karnataka, India",
                job_id="j1",
            ),
            _MockJob(
                title="Frontend Dev",
                location="Bangalore, Karnataka, India",
                job_id="j2",
            ),
            _MockJob(
                title="Frontend Dev",
                location="Mumbai, Maharashtra, India",
                job_id="j3",
            ),
            _MockJob(title="Frontend Dev", location="Remote", job_id="j4"),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        # Default: remote/WFH listings pass alongside the city.
        report = await service.generate_daily_report(location="Bengaluru")

        locs = sorted(str(j["location"]) for j in report["new_jobs"])
        assert locs == [
            "Bangalore, Karnataka, India",
            "Bengaluru, Karnataka, India",
            "Remote",
        ]
        assert report["summary"]["new_jobs"] == 3

        # Opted out: remote jobs are dropped, only the city remains.
        strict = await service.generate_daily_report(
            location="Bengaluru",
            include_remote=False,
        )
        assert sorted(str(j["location"]) for j in strict["new_jobs"]) == [
            "Bangalore, Karnataka, India",
            "Bengaluru, Karnataka, India",
        ]

    @pytest.mark.asyncio
    async def test_location_filter_excludes_other_city(self):
        """A Chennai-only digest never includes Bengaluru or Remote jobs."""
        service = ReportService(MagicMock())
        service.job_repo = AsyncMock()
        service.job_repo.get_recent_jobs.return_value = [
            _MockJob(title="Frontend Dev", location="Bengaluru, India", job_id="j1"),
            _MockJob(title="Frontend Dev", location="Chennai, India", job_id="j2"),
            _MockJob(title="Frontend Dev", location="Remote", job_id="j3"),
        ]
        service.app_repo = AsyncMock()
        service.app_repo.get_recent_applications.return_value = []
        service.app_repo.get_status_counts.return_value = {}
        service.app_repo.get_applied_job_ids.return_value = set()
        service.job_repo.get_closing_soon.return_value = []

        report = await service.generate_daily_report(
            location="Chennai",
            include_remote=False,
        )

        assert [str(j["location"]) for j in report["new_jobs"]] == [
            "Chennai, India",
        ]


class TestClassifyDomain:
    """Tests for the domain classifier used in alert sections."""

    def test_security_domain_wins(self):
        from interntrack.services.report_service import classify_domain

        assert classify_domain("SOC Analyst", []) == "security"
        assert classify_domain("Penetration Tester / VAPT", []) == "security"
        assert classify_domain("DevSecOps Engineer", []) == "security"
        assert classify_domain("Information Security Manager") == "security"

    def test_security_keywords_cover_modern_titles(self):
        """GRC / threat intel / OSINT / DFIR / web-app titles classify security."""
        from interntrack.services.report_service import classify_domain

        for title in [
            "GRC Analyst",
            "Threat Intelligence Analyst",
            "Penetration Tester",
            "OSINT Investigator",
            "DFIR Consultant",
            "Forensic Analyst",
            "Bug Bounty Hunter",
            "Cloud Security Engineer",
            "Network Security Administrator",
            "Zero Trust Architect",
            "CISSP Certified Analyst",
            "Security Operations Center Lead",
            "Exploit Developer",
            "CTF Player",
        ]:
            assert classify_domain(title, []) == "security", title

    def test_webapp_attack_terms_classify_security(self):
        """SQLi / XSS titles are security, not coding/data."""
        from interntrack.services.report_service import classify_domain

        assert classify_domain("Web Application Security (SQLi)", []) == "security"
        assert classify_domain("Security Engineer - XSS Research", []) == "security"

    def test_sql_developer_still_coding(self):
        """Plain SQL dev roles must NOT be dragged into security."""
        from interntrack.services.report_service import classify_domain

        assert classify_domain("SQL Developer", []) == "coding"
        assert classify_domain("Senior SQL Developer", []) == "coding"

    def test_company_prefix_does_not_leak_into_domain(self):
        """Only the role after 'Company: ' is classified."""
        from interntrack.services.report_service import classify_domain

        # "Keeper Security" in the company prefix must not make this a
        # security role — the actual role is Account Manager.
        assert classify_domain("Keeper Security: Account Manager", []) == "marketing"
        assert classify_domain("SecureCorp: Python Developer", []) == "coding"
        assert classify_domain("Acme: SOC Analyst", []) == "security"

    def test_coding_domain(self):
        from interntrack.services.report_service import classify_domain

        assert classify_domain("Senior Python Developer", []) == "coding"
        assert classify_domain("Full Stack Engineer", []) == "coding"
        assert classify_domain("Data Engineer", []) == "coding"

    def test_hardware_domain(self):
        """Hardware / embedded / PCB / RF titles land in the hardware bucket
        — and win over generic software words when both appear."""
        from interntrack.services.report_service import classify_domain

        for title in [
            "Hardware Engineer",
            "Embedded Systems Engineer",
            "Embedded Software Engineer",
            "PCB Design Engineer",
            "RF Engineer",
            "VLSI Design Engineer",
            "FPGA Engineer",
            "Hardware Test Engineer",
            "Electronics Engineer",
            "Firmware Engineer",
            "LabVIEW Developer",
        ]:
            assert classify_domain(title, []) == "hardware", title
        # Tags give hardware context to otherwise-generic titles.
        assert (
            classify_domain("Engineer", ["embedded", "microcontroller"]) == "hardware"
        )

    def test_software_testing_stays_coding(self):
        """QA / software-testing roles must NOT be dragged into hardware."""
        from interntrack.services.report_service import classify_domain

        for title in [
            "Software Test Engineer",
            "QA Engineer",
            "Test Automation Engineer",
            "Software Tester",
            "SDET",
            "Testing Engineer",
        ]:
            assert classify_domain(title, []) == "coding", title

    def test_hardware_accepted_by_alert_normalization(self):
        """The registration / preferences path accepts the hardware domain."""
        from interntrack.api.v1.notifications import _normalize_domains

        assert _normalize_domains(["hardware", "coding", "bogus"]) == [
            "hardware",
            "coding",
        ]

    def test_frontend_domain(self):
        """Frontend-flavoured roles land in the frontend bucket, not coding."""
        from interntrack.services.report_service import classify_domain

        assert classify_domain("Frontend Developer", []) == "frontend"
        assert classify_domain("Front-End Engineer", []) == "frontend"
        assert classify_domain("React Developer", []) == "frontend"
        assert classify_domain("Angular Developer", []) == "frontend"
        assert classify_domain("UI Developer", []) == "frontend"
        # Pure backend / full-stack roles stay in coding.
        assert classify_domain("Backend Engineer", []) == "coding"
        assert classify_domain("Full Stack Developer", []) == "coding"
        # Security still wins over frontend when both appear.
        assert classify_domain("Frontend Security Engineer", []) == "security"

    def test_frontend_accepted_by_alert_normalization(self):
        """The registration / preferences path accepts the frontend domain."""
        from interntrack.api.v1.notifications import _normalize_domains

        assert _normalize_domains(["frontend", "coding", "bogus"]) == [
            "frontend",
            "coding",
        ]

    def test_other_domains(self):
        from interntrack.services.report_service import classify_domain

        assert classify_domain("Data Analyst", []) == "data"
        assert classify_domain("UX Designer", []) == "design"
        assert classify_domain("Account Executive", []) == "marketing"
        assert classify_domain("Accountant", []) == "finance"
        assert classify_domain("Random Unknown Role", []) == "other"

    def test_tags_contribute_to_classification(self):
        from interntrack.services.report_service import classify_domain

        assert classify_domain("Analyst", ["security", "siem"]) == "security"
        assert classify_domain("Specialist", ["python", "kubernetes"]) == "coding"


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
