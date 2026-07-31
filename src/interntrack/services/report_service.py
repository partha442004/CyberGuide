"""
Report service for generating daily, weekly, and monthly reports.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import ReportType
from interntrack.repositories.application_repository import ApplicationRepository
from interntrack.repositories.job_repository import JobRepository


class ReportService:
    """Report service for generating analytics reports."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
        self.app_repo = ApplicationRepository(session)
        self.jinja_env = Environment(
            loader=FileSystemLoader("src/interntrack/reports/templates")
        )

    async def generate_daily_report(self) -> Dict[str, Any]:
        """Generate daily report."""
        new_jobs = await self.job_repo.get_recent_jobs(days=1)
        new_apps = await self.app_repo.get_recent_applications(days=1)
        status_counts = await self.app_repo.get_status_counts()

        return {
            "report_type": "daily",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "new_jobs": len(new_jobs),
                "new_applications": len(new_apps),
                "total_applications": sum(status_counts.values()),
            },
            "new_jobs": [
                {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                }
                for job in new_jobs[:10]
            ],
            "closing_soon": [
                {
                    "title": job.title,
                    "company": job.company,
                    "expires_at": job.expires_at.isoformat() if job.expires_at else None,
                }
                for job in await self.job_repo.get_closing_soon(days=2)
            ],
            "application_status": status_counts,
        }

    async def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly report."""
        new_jobs = await self.job_repo.get_recent_jobs(days=7)
        new_apps = await self.app_repo.get_recent_applications(days=7)
        status_counts = await self.app_repo.get_status_counts()
        top_companies = await self.job_repo.get_top_companies(limit=10)
        job_types = await self.job_repo.get_job_type_distribution()

        return {
            "report_type": "weekly",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "new_jobs": len(new_jobs),
                "new_applications": len(new_apps),
                "total_applications": sum(status_counts.values()),
                "rejection_rate": await self.app_repo.get_rejection_rate(),
                "response_rate": await self.app_repo.get_response_rate(),
            },
            "top_companies": [
                {"company": company, "jobs": count}
                for company, count in top_companies
            ],
            "job_type_distribution": [
                {"type": jtype.value, "count": count}
                for jtype, count in job_types
            ],
            "application_timeline": await self.app_repo.get_application_timeline(days=7),
            "application_status": status_counts,
        }

    async def generate_monthly_report(self) -> Dict[str, Any]:
        """Generate monthly report with complete analytics."""
        weekly_report = await self.generate_weekly_report()
        new_jobs = await self.job_repo.get_recent_jobs(days=30)
        salary_stats = await self.job_repo.get_salary_statistics()

        return {
            **weekly_report,
            "report_type": "monthly",
            "salary_statistics": salary_stats,
            "monthly_applications": await self.app_repo.get_recent_applications(days=30),
        }

    async def render_report(self, report_data: Dict[str, Any]) -> str:
        """Render report to HTML."""
        report_type = report_data.get("report_type", "daily")
        template = self.jinja_env.get_template(f"{report_type}_report.html")
        return template.render(**report_data)
