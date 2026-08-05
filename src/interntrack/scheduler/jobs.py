"""
Scheduled background jobs.
"""

from datetime import UTC, datetime

from interntrack.database.session import get_db_session
from interntrack.services.job_service import JobService
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService


async def run_job_discovery():
    """Periodic job discovery from all sources."""
    async with get_db_session() as session:
        from interntrack.scrapers.registry import get_default_registry

        service = JobService(session)
        registry = get_default_registry()

        jobs = await registry.fetch_all(query="python developer")
        saved = await service.save_jobs(jobs)
        print(f"[{datetime.now(UTC)}] Discovery: {len(jobs)} found, {len(saved)} saved")


async def generate_daily_report():
    """Generate and send daily report."""
    async with get_db_session() as session:
        service = ReportService(session)
        report = await service.generate_daily_report()

        # Send notification
        manager = NotificationManager(session)
        message = await build_daily_report_message(report, session)
        await manager.notify_all(message, subject="Daily Report")


def format_daily_report(report: dict) -> str:
    """Format daily report summary counts for notification."""
    summary = report.get("summary", {})
    return (
        f"📊 Daily Report\n\n"
        f"New Jobs: {summary.get('new_jobs', 0)}\n"
        f"New Applications: {summary.get('new_applications', 0)}\n"
        f"Total Applications: {summary.get('total_applications', 0)}"
    )


async def _latest_resume_skill_names(session) -> set | None:
    """Load the most recently parsed resume's skill names, if any."""
    try:
        from sqlalchemy import select

        from cybershield.api.v1.resumes import _extract_skill_names
        from cybershield.domain.models import ResumeData

        result = await session.execute(
            select(ResumeData).order_by(ResumeData.updated_at.desc()).limit(1)
        )
        resume = result.scalar_one_or_none()
        if resume:
            return _extract_skill_names(resume.skills)
    except Exception:
        return None
    return None


def _job_match_score(resume_skills: set | None, job: dict) -> float | None:
    """Match % for a job against the resume skills, or None when unknown."""
    if not resume_skills:
        return None
    try:
        from cybershield.api.v1.resumes import _calculate_job_match, _JobMatchData

        job_data = _JobMatchData(
            id=str(job.get("id") or ""),
            title=job.get("title"),
            company=job.get("company"),
            required_skills=job.get("required_skills") or [],
            preferred_skills=job.get("preferred_skills") or [],
            tags=job.get("tags") or [],
        )
        result = _calculate_job_match(resume_skills, job_data)
        if result.match_score is None:
            return None
        return float(result.match_score)
    except Exception:
        return None


async def build_daily_report_message(report: dict, session) -> str:
    """Rich daily-report notification: summary counts plus the top new jobs
    with their apply links and the user's match % (best matches first).
    """
    lines = [format_daily_report(report)]
    jobs = report.get("new_jobs") or []
    if not jobs:
        return "\n".join(lines)

    resume_skills = await _latest_resume_skill_names(session)

    lines.append("")
    lines.append("🆕 New jobs found:")
    scored = [(_job_match_score(resume_skills, job), job) for job in jobs]
    scored.sort(key=lambda item: (item[0] is None, -(item[0] or 0.0)))

    for score, job in scored:
        title = (job.get("title") or "Untitled")[:90]
        company = job.get("company") or ""
        url = job.get("url") or ""
        head = f"🎯 [{score:.0f}%] {title}" if score is not None else f"💼 {title}"
        if company:
            head += f" — {company}"
        lines.append(head)
        if url:
            lines.append(f"   🔗 Apply: {url}")

    lines.append("")
    lines.append(
        "Match % = how well your uploaded resume fits each job (best matches first)."
    )
    return "\n".join(lines)


async def verify_job_links():
    """Verify job links are still active."""
    async with get_db_session() as session:
        from interntrack.engines.verification import VerificationEngine

        engine = VerificationEngine(session)
        results = await engine.verify_all_links()

        dead_links = [r for r in results if not r.get("is_alive")]
        if dead_links:
            print(f"[{datetime.now(UTC)}] Found {len(dead_links)} dead links")


async def deactivate_expired_jobs():
    """Deactivate expired job listings."""
    async with get_db_session() as session:
        service = JobService(session)
        count = await service.deactivate_expired()
        if count > 0:
            print(f"[{datetime.now(UTC)}] Deactivated {count} expired jobs")
