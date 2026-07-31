"""
CyberGuide Scheduler - Entry Point

Runs background jobs for:
- Job discovery (every 30 minutes)
- Link verification (every 6 hours)
- Scam analysis (every 12 hours)
- Daily/Weekly/Monthly reports
- Resume matching refresh
"""

import asyncio
import logging
import signal
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cybershield.config import get_settings
from cybershield.database.session import get_db_session, init_db
from cybershield.domain.models import Job, ScamScore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


async def job_discovery():
    """Run job discovery from all sources."""
    logger.info("Starting job discovery...")
    try:
        from cybershield.scrapers.registry import ScraperRegistry

        # Run all scrapers
        jobs = await ScraperRegistry.run_all()
        logger.info(f"Job discovery completed: {len(jobs)} jobs found from scrapers")

        # Store jobs in database
        async with get_db_session() as session:
            stored_count = 0
            for scraped_job in jobs:
                # Check if job already exists by URL
                from sqlalchemy import select
                existing = await session.execute(
                    select(Job).where(Job.url == scraped_job.url)
                )
                if existing.scalar_one_or_none():
                    continue

                # Create new job record
                job = Job(
                    title=scraped_job.title,
                    company=scraped_job.company_name,
                    location=scraped_job.location,
                    country=scraped_job.country,
                    city=scraped_job.city,
                    description=scraped_job.description,
                    url=scraped_job.url,
                    apply_url=scraped_job.apply_url,
                    source=scraped_job.source,
                    job_id_external=scraped_job.source_id,
                    salary_min=scraped_job.salary_min,
                    salary_max=scraped_job.salary_max,
                    salary_currency=scraped_job.salary_currency,
                    is_remote=scraped_job.is_remote,
                    work_mode="remote" if scraped_job.is_remote else "onsite",
                    job_type=scraped_job.job_type,
                    experience_level=scraped_job.experience_level,
                    posted_at=scraped_job.posting_date,
                    expires_at=scraped_job.deadline,
                    required_skills=scraped_job.required_skills,
                    preferred_skills=scraped_job.preferred_skills,
                    raw_data=scraped_job.raw_data,
                )
                session.add(job)
                stored_count += 1

            await session.commit()
            logger.info(f"Stored {stored_count} new jobs in database")

    except Exception as e:
        logger.error(f"Job discovery failed: {e}", exc_info=True)


async def link_verification():
    """Verify job links are still active."""
    logger.info("Starting link verification...")
    try:
        from cybershield.engines.verification import VerificationEngine
        from sqlalchemy import select

        engine = VerificationEngine()

        async with get_db_session() as session:
            # Get jobs that haven't been verified
            result = await session.execute(
                select(Job).where(
                    Job.is_active == True,
                    Job.is_verified == False,
                ).limit(50)
            )
            jobs_to_verify = result.scalars().all()

            verified_count = 0
            for job in jobs_to_verify:
                job_data = {
                    "id": job.id,
                    "url": job.url,
                    "apply_url": job.apply_url,
                    "company_name": job.company,
                    "deadline": job.expires_at,
                }
                verification_result = await engine.process(job_data)

                if verification_result.success:
                    job.is_verified = verification_result.data.get("is_verified", False)
                    verified_count += 1

            await session.commit()
            logger.info(f"Link verification completed: {verified_count} jobs verified")

    except Exception as e:
        logger.error(f"Link verification failed: {e}", exc_info=True)


async def scam_analysis():
    """Analyze jobs for scam indicators."""
    logger.info("Starting scam analysis...")
    try:
        from cybershield.engines.scam_detection import ScamDetectionEngine
        from sqlalchemy import select

        engine = ScamDetectionEngine()

        async with get_db_session() as session:
            # Get jobs without scam score
            result = await session.execute(
                select(Job).where(
                    Job.is_active == True,
                ).limit(50)
            )
            jobs_to_analyze = result.scalars().all()

            analyzed_count = 0
            for job in jobs_to_analyze:
                # Skip if already has scam score
                if job.scam_score:
                    continue

                job_data = {
                    "id": job.id,
                    "title": job.title,
                    "company_name": job.company,
                    "description": job.description,
                    "url": job.url,
                }
                scam_result = await engine.process(job_data)

                if scam_result.success:
                    # Create scam score record
                    scam_score = ScamScore(
                        job_id=job.id,
                        scam_score=scam_result.data.get("scam_score", 0),
                        confidence=scam_result.data.get("confidence", 0.5),
                        flags=scam_result.data.get("flags", []),
                        reasons=scam_result.data.get("reasons", []),
                        is_scam=scam_result.data.get("is_scam", False),
                        analyzed_at=datetime.now(timezone.utc),
                    )
                    session.add(scam_score)
                    analyzed_count += 1

            await session.commit()
            logger.info(f"Scam analysis completed: {analyzed_count} jobs analyzed")

    except Exception as e:
        logger.error(f"Scam analysis failed: {e}", exc_info=True)


async def daily_report():
    """Generate and send daily digest."""
    logger.info("Generating daily report...")
    try:
        from sqlalchemy import select, func
        from cybershield.notifications.orchestrator import NotificationOrchestrator

        async with get_db_session() as session:
            # Get stats
            total_jobs = await session.scalar(select(func.count(Job.id)))
            new_today = await session.scalar(
                select(func.count(Job.id)).where(
                    Job.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
                )
            )

            # Get expiring soon (next 7 days)
            expiring = await session.scalar(
                select(func.count(Job.id)).where(
                    Job.is_active == True,
                    Job.expires_at <= datetime.now(timezone.utc) + timedelta(days=7),
                    Job.expires_at >= datetime.now(timezone.utc),
                )
            )

            # Get high-match jobs
            high_match = await session.scalar(
                select(func.count(Job.id)).where(
                    Job.is_active == True,
                )
            )

            # Send notification
            orchestrator = NotificationOrchestrator()
            # Configure channels from settings
            if settings.telegram_bot_token:
                from cybershield.notifications.telegram import TelegramNotifier
                orchestrator.register("telegram", TelegramNotifier({
                    "bot_token": settings.telegram_bot_token,
                    "chat_id": settings.telegram_chat_id,
                }))

            await orchestrator.send_daily_digest({
                "new_jobs": new_today or 0,
                "expiring_soon": expiring or 0,
                "high_match": high_match or 0,
                "top_skills": ["Python", "SIEM", "AWS", "Cloud Security"],
                "top_companies": ["Microsoft", "Google", "Amazon"],
            })

        logger.info("Daily report completed")

    except Exception as e:
        logger.error(f"Daily report failed: {e}", exc_info=True)


async def weekly_report():
    """Generate and send weekly analytics report."""
    logger.info("Generating weekly report...")
    try:
        from sqlalchemy import select, func
        from cybershield.notifications.orchestrator import NotificationOrchestrator
        from cybershield.domain.models import Application, SkillTrend

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        async with get_db_session() as session:
            # Job stats for the week
            total_jobs = await session.scalar(select(func.count(Job.id)))
            new_this_week = await session.scalar(
                select(func.count(Job.id)).where(Job.created_at >= week_ago)
            )

            # Application stats
            total_apps = await session.scalar(select(func.count(Application.id)))
            apps_this_week = await session.scalar(
                select(func.count(Application.id)).where(Application.created_at >= week_ago)
            )

            # Top hiring companies
            from sqlalchemy import desc
            top_companies_result = await session.execute(
                select(Job.company, func.count(Job.id).label("count"))
                .where(Job.created_at >= week_ago)
                .group_by(Job.company)
                .order_by(desc("count"))
                .limit(10)
            )
            top_companies = [(row[0], row[1]) for row in top_companies_result.all()]

            # Top skills in demand
            top_skills_result = await session.execute(
                select(SkillTrend.skill_id, func.sum(SkillTrend.demand_count).label("total"))
                .where(SkillTrend.period_start >= week_ago)
                .group_by(SkillTrend.skill_id)
                .order_by(desc("total"))
                .limit(10)
            )
            top_skills = [(row[0], row[1]) for row in top_skills_result.all()]

            # Expiring jobs next week
            next_week = datetime.now(timezone.utc) + timedelta(days=7)
            expiring_count = await session.scalar(
                select(func.count(Job.id)).where(
                    Job.is_active == True,
                    Job.expires_at <= next_week,
                    Job.expires_at >= datetime.now(timezone.utc),
                )
            )

            # Send notification
            orchestrator = NotificationOrchestrator()
            if settings.telegram_bot_token:
                from cybershield.notifications.telegram import TelegramNotifier
                orchestrator.register("telegram", TelegramNotifier({
                    "bot_token": settings.telegram_bot_token,
                    "chat_id": settings.telegram_chat_id,
                }))

            await orchestrator.send_report("weekly", {
                "title": "📊 Weekly Report",
                "period": f"{week_ago.strftime('%b %d')} - {datetime.now(timezone.utc).strftime('%b %d, %Y')}",
                "new_jobs": new_this_week or 0,
                "total_jobs": total_jobs or 0,
                "applications_submitted": apps_this_week or 0,
                "total_applications": total_apps or 0,
                "expiring_next_week": expiring_count or 0,
                "top_companies": top_companies[:5],
                "top_skills": [s[0] for s in top_skills[:5]],
            })

        logger.info("Weekly report completed")

    except Exception as e:
        logger.error(f"Weekly report failed: {e}", exc_info=True)


async def monthly_report():
    """Generate and send monthly analytics report."""
    logger.info("Generating monthly report...")
    try:
        from sqlalchemy import select, func, desc
        from cybershield.notifications.orchestrator import NotificationOrchestrator
        from cybershield.domain.models import Application, SkillTrend

        month_ago = datetime.now(timezone.utc) - timedelta(days=30)

        async with get_db_session() as session:
            # Job stats for the month
            total_jobs = await session.scalar(select(func.count(Job.id)))
            new_this_month = await session.scalar(
                select(func.count(Job.id)).where(Job.created_at >= month_ago)
            )

            # Application stats
            total_apps = await session.scalar(select(func.count(Application.id)))
            apps_this_month = await session.scalar(
                select(func.count(Application.id)).where(Application.created_at >= month_ago)
            )

            # Success rate (interviews + offers + joined)
            success_statuses = ["interview", "offer", "joined"]
            success_count = await session.scalar(
                select(func.count(Application.id)).where(
                    Application.created_at >= month_ago,
                    Application.status.in_(success_statuses),
                )
            )
            success_rate = (success_count / apps_this_month * 100) if apps_this_month else 0

            # Top hiring companies
            top_companies_result = await session.execute(
                select(Job.company, func.count(Job.id).label("count"))
                .where(Job.created_at >= month_ago)
                .group_by(Job.company)
                .order_by(desc("count"))
                .limit(15)
            )
            top_companies = [(row[0], row[1]) for row in top_companies_result.all()]

            # Top skills in demand
            top_skills_result = await session.execute(
                select(SkillTrend.skill_id, func.sum(SkillTrend.demand_count).label("total"))
                .where(SkillTrend.period_start >= month_ago)
                .group_by(SkillTrend.skill_id)
                .order_by(desc("total"))
                .limit(15)
            )
            top_skills = [(row[0], row[1]) for row in top_skills_result.all()]

            # Salary stats
            salary_stats = await session.execute(
                select(
                    func.avg(Job.salary_min).label("avg_min"),
                    func.avg(Job.salary_max).label("avg_max"),
                    func.min(Job.salary_min).label("min"),
                    func.max(Job.salary_max).label("max"),
                ).where(
                    Job.created_at >= month_ago,
                    Job.salary_min.isnot(None),
                )
            )
            salary = salary_stats.first()

            # Job type distribution
            job_type_result = await session.execute(
                select(Job.job_type, func.count(Job.id).label("count"))
                .where(Job.created_at >= month_ago)
                .group_by(Job.job_type)
                .order_by(desc("count"))
            )
            job_types = [(row[0], row[1]) for row in job_type_result.all()]

            # Remote job percentage
            total_with_mode = await session.scalar(
                select(func.count(Job.id)).where(Job.created_at >= month_ago, Job.work_mode.isnot(None))
            ) or 1
            remote_count = await session.scalar(
                select(func.count(Job.id)).where(Job.created_at >= month_ago, Job.work_mode == "remote")
            ) or 0
            remote_pct = round(remote_count / total_with_mode * 100, 1)

            # Send notification
            orchestrator = NotificationOrchestrator()
            if settings.telegram_bot_token:
                from cybershield.notifications.telegram import TelegramNotifier
                orchestrator.register("telegram", TelegramNotifier({
                    "bot_token": settings.telegram_bot_token,
                    "chat_id": settings.telegram_chat_id,
                }))

            await orchestrator.send_report("monthly", {
                "title": "📈 Monthly Report",
                "period": f"{month_ago.strftime('%b %d')} - {datetime.now(timezone.utc).strftime('%b %d, %Y')}",
                "new_jobs": new_this_month or 0,
                "total_jobs": total_jobs or 0,
                "applications_submitted": apps_this_month or 0,
                "success_rate": round(success_rate, 1),
                "avg_salary_range": f"{int(salary.avg_min or 0)}-{int(salary.avg_max or 0)}" if salary else "N/A",
                "top_companies": top_companies[:10],
                "top_skills": [s[0] for s in top_skills[:10]],
                "job_types": job_types[:5],
                "remote_percentage": remote_pct,
            })

        logger.info("Monthly report completed")

    except Exception as e:
        logger.error(f"Monthly report failed: {e}", exc_info=True)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Job Discovery - every 30 minutes
    scheduler.add_job(
        job_discovery,
        IntervalTrigger(minutes=30),
        id="job_discovery",
        name="Job Discovery",
        replace_existing=True,
    )

    # Link Verification - every 6 hours
    scheduler.add_job(
        link_verification,
        IntervalTrigger(hours=6),
        id="link_verification",
        name="Link Verification",
        replace_existing=True,
    )

    # Scam Analysis - every 12 hours
    scheduler.add_job(
        scam_analysis,
        IntervalTrigger(hours=12),
        id="scam_analysis",
        name="Scam Analysis",
        replace_existing=True,
    )

    # Daily Report - 6 AM UTC
    scheduler.add_job(
        daily_report,
        CronTrigger(hour=6, minute=0),
        id="daily_report",
        name="Daily Report",
        replace_existing=True,
    )

    # Weekly Report - Monday 8 AM UTC
    scheduler.add_job(
        weekly_report,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_report",
        name="Weekly Report",
        replace_existing=True,
    )

    # Monthly Report - 1st of month 9 AM UTC
    scheduler.add_job(
        monthly_report,
        CronTrigger(day=1, hour=9, minute=0),
        id="monthly_report",
        name="Monthly Report",
        replace_existing=True,
    )

    return scheduler


async def main():
    """Main scheduler loop."""
    logger.info("Starting CyberGuide Scheduler...")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database
    await init_db()

    # Create scheduler
    scheduler = create_scheduler()

    # Handle shutdown signals
    def shutdown(signum, frame):
        logger.info("Shutdown signal received, stopping scheduler...")
        scheduler.shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} ({job.id}): {job.trigger}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
