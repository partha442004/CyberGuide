"""
Report service for generating daily, weekly, and monthly reports.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.repositories.application_repository import ApplicationRepository
from interntrack.repositories.job_repository import JobRepository
from interntrack.utils.helpers import to_naive_utc, utcnow

# Resolve the template directory relative to this module so rendering works
# regardless of the current working directory.
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"

# Job domain classification for alert sections. Order matters: the first
# matching domain wins (security checked first so "Security Analyst" is never
# swallowed by the generic coding bucket).
_DOMAIN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "security",
        (
            "security",
            "cyber",
            "soc",
            "pentest",
            "vapt",
            "infosec",
            "appsec",
            "devsecops",
            "siem",
            "malware",
            "threat",
            "vulnerab",
            "incident response",
            "red team",
            "blue team",
            "ethical hack",
            "information security",
        ),
    ),
    (
        "coding",
        (
            "software",
            "developer",
            "engineer",
            "programmer",
            "backend",
            "frontend",
            "full stack",
            "fullstack",
            "devops",
            "sre",
            "python",
            "javascript",
            "typescript",
            "java",
            "react",
            "node",
            "sql",
            "data engineer",
            "machine learning",
            "data scientist",
            "ai",
            "architect",
        ),
    ),
    (
        "data",
        (
            "data",
            "analyst",
            "analytics",
            "bi ",
            "business intelligence",
            "database",
        ),
    ),
    (
        "design",
        ("designer", "ux", "ui ", "graphic", "visual", "product design"),
    ),
    ("finance", ("finance", "accountant", "accounting", "audit", "tax", "bookkeep")),
    (
        "marketing",
        (
            "marketing",
            "sales",
            "account",
            "growth",
            "content",
            "social media",
            "brand",
            "seo",
            "customer success",
            "business development",
        ),
    ),
]


def classify_domain(title: str, tags: list | None = None) -> str:
    """Classify a job into a domain bucket for alert sections.

    RSS feeds prefix titles with the company name ("Acme Corp: Security
    Engineer"), so only the role part after the first ": " is classified to
    stop a company name like "Keeper Security" from dragging its sales roles
    into the security bucket.
    """
    raw = f"{title or ''}"
    role = raw.split(": ", 1)[-1] if ": " in raw else raw
    text = role.lower()
    if tags:
        text += " " + " ".join(str(t).lower() for t in tags)
    for domain, keywords in _DOMAIN_KEYWORDS:
        if any(k in text for k in keywords):
            return domain
    return "other"


class ReportService:
    """Report service for generating analytics reports."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
        self.app_repo = ApplicationRepository(session)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    @staticmethod
    def _as_datetime(value) -> datetime | None:
        """Narrow an ORM attribute to a datetime (mypy-friendly)."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return None

    @staticmethod
    def _fmt_dt(value) -> str | None:
        """Format an ORM datetime attribute to ISO-8601 (mypy-friendly)."""
        dt = ReportService._as_datetime(value)
        if dt is None:
            return None
        naive = to_naive_utc(dt)
        if naive is None:
            return None
        return naive.isoformat()

    @staticmethod
    def _job_age_days(job) -> int:
        """Whole days since the job was posted (0 = today)."""
        posted = ReportService._as_datetime(
            getattr(job, "posted_at", None) or getattr(job, "created_at", None)
        )
        if posted is None:
            return 0
        posted = to_naive_utc(posted)
        if posted is None:
            return 0
        age = (utcnow() - posted).total_seconds() / 86400
        return max(0, int(age))

    async def generate_daily_report(
        self,
        domains: list[str] | None = None,
        min_match_score: int | None = None,
    ) -> dict[str, Any]:
        """Generate daily report.

        Jobs are listed over a 7-day window so the alert can group them by
        how recently they were posted (today / 1 day ago / older), and each
        entry carries its expiry info (``expires_at``, ``is_active``) so the
        message can flag closing-soon and expired listings.

        ``domains`` optionally restricts the report to the given domain keys
        (security, coding, ...) — the summary counts then reflect the
        filtered set. ``min_match_score`` is carried through so the alert
        message can drop jobs whose resume match % is below the threshold.
        """
        recent_jobs = await self.job_repo.get_recent_jobs(days=7)
        new_apps = await self.app_repo.get_recent_applications(days=1)
        status_counts = await self.app_repo.get_status_counts()
        applied_ids = await self.app_repo.get_applied_job_ids()

        jobs = [
            {
                "id": str(getattr(job, "id", "")),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "tags": list(getattr(job, "tags", None) or []),
                "required_skills": list(getattr(job, "required_skills", None) or []),
                "preferred_skills": list(getattr(job, "preferred_skills", None) or []),
                "posted_at": self._fmt_dt(getattr(job, "posted_at", None)),
                "created_at": self._fmt_dt(getattr(job, "created_at", None)),
                "expires_at": self._fmt_dt(getattr(job, "expires_at", None)),
                "is_active": bool(getattr(job, "is_active", True)),
                "is_applied": str(getattr(job, "id", "")) in applied_ids,
                "domain": classify_domain(
                    str(getattr(job, "title", "")),
                    list(getattr(job, "tags", None) or []),
                ),
                "age_days": self._job_age_days(job),
            }
            for job in recent_jobs[:25]
        ]
        if domains:
            jobs = [job for job in jobs if job["domain"] in domains]

        return {
            "report_type": "daily",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "new_jobs": len(jobs),
                "new_applications": len(new_apps),
                "total_applications": sum(status_counts.values()),
            },
            "new_jobs": jobs,
            "min_match_score": min_match_score,
            "closing_soon": [
                {
                    "title": job.title,
                    "company": job.company,
                    "expires_at": self._fmt_dt(job.expires_at),
                }
                for job in await self.job_repo.get_closing_soon(days=2)
            ],
            "application_status": status_counts,
        }

    async def generate_weekly_report(self) -> dict[str, Any]:
        """Generate weekly report."""
        new_jobs = await self.job_repo.get_recent_jobs(days=7)
        new_apps = await self.app_repo.get_recent_applications(days=7)
        status_counts = await self.app_repo.get_status_counts()
        top_companies = await self.job_repo.get_top_companies(limit=10)
        job_types = await self.job_repo.get_job_type_distribution()

        return {
            "report_type": "weekly",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "new_jobs": len(new_jobs),
                "new_applications": len(new_apps),
                "total_applications": sum(status_counts.values()),
                "rejection_rate": await self.app_repo.get_rejection_rate(),
                "response_rate": await self.app_repo.get_response_rate(),
            },
            "top_companies": [
                {"company": company, "jobs": count} for company, count in top_companies
            ],
            "job_type_distribution": [
                {"type": jtype.value, "count": count} for jtype, count in job_types
            ],
            "application_timeline": await self.app_repo.get_application_timeline(
                days=7,
            ),
            "application_status": status_counts,
        }

    async def generate_monthly_report(self) -> dict[str, Any]:
        """Generate monthly report with complete analytics."""
        weekly_report = await self.generate_weekly_report()
        await self.job_repo.get_recent_jobs(days=30)
        salary_stats = await self.job_repo.get_salary_statistics()

        return {
            **weekly_report,
            "report_type": "monthly",
            "salary_statistics": salary_stats,
            "monthly_applications": await self.app_repo.get_recent_applications(
                days=30,
            ),
        }

    async def render_report(self, report_data: dict[str, Any]) -> str:
        """Render report to HTML."""
        report_type = report_data.get("report_type", "daily")
        template = self.jinja_env.get_template(f"{report_type}_report.html")
        return template.render(**report_data)
