"""
Scheduled background jobs.
"""

import asyncio
from datetime import datetime, timezone

from interntrack.database.session import get_db_session
from interntrack.services.job_service import JobService
from interntrack.services.report_service import ReportService
from interntrack.services.notification_service import NotificationManager


async def run_job_discovery():
    """Periodic job discovery from all sources."""
    async with get_db_session() as session:
        from interntrack.scrapers.registry import get_default_registry

        service = JobService(session)
        registry = get_default_registry()

        jobs = await registry.fetch_all(query="python developer")
        saved = await service.save_jobs(jobs)
        print(f"[{datetime.now(timezone.utc)}] Discovery: {len(jobs)} found, {len(saved)} saved")


async def generate_daily_report():
    """Generate and send daily report."""
    async with get_db_session() as session:
        service = ReportService(session)
        report = await service.generate_daily_report()

        # Send notification
        manager = NotificationManager(session)
        message = format_daily_report(report)
        await manager.notify_all(message, subject="Daily Report")


def format_daily_report(report: dict) -> str:
    """Format daily report for notification."""
    summary = report.get("summary", {})
    return (
        f"📊 Daily Report\n\n"
        f"New Jobs: {summary.get('new_jobs', 0)}\n"
        f"New Applications: {summary.get('new_applications', 0)}\n"
        f"Total Applications: {summary.get('total_applications', 0)}"
    )


async def verify_job_links():
    """Verify job links are still active."""
    async with get_db_session() as session:
        from interntrack.engines.verification import VerificationEngine

        engine = VerificationEngine(session)
        results = await engine.verify_all_links()

        dead_links = [r for r in results if not r.get("is_alive")]
        if dead_links:
            print(f"[{datetime.now(timezone.utc)}] Found {len(dead_links)} dead links")


async def deactivate_expired_jobs():
    """Deactivate expired job listings."""
    async with get_db_session() as session:
        service = JobService(session)
        count = await service.deactivate_expired()
        if count > 0:
            print(f"[{datetime.now(timezone.utc)}] Deactivated {count} expired jobs")
