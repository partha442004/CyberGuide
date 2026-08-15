"""
Scheduler setup with APScheduler.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from interntrack.config import get_settings
from interntrack.scheduler.jobs import (
    deactivate_expired_jobs,
    generate_daily_report,
    record_match_snapshots,
    run_job_discovery,
    send_closing_soon_alerts,
    send_daily_owner_summary,
    send_follow_up_nudges,
    send_interview_reminders,
    verify_job_links,
)

settings = get_settings()

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Configure and start the scheduler."""
    # Job discovery every 30 minutes
    scheduler.add_job(
        run_job_discovery,
        IntervalTrigger(minutes=settings.scrape_interval_minutes),
        id="job_discovery",
        name="Job Discovery",
        replace_existing=True,
    )

    # Daily report at 6 AM
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=6, minute=0),
        id="daily_report",
        name="Daily Report",
        replace_existing=True,
    )

    # Weekly report on Monday at 8 AM — the real weekly digest: a 7-day
    # recap with most-engaged jobs + team snapshot, honoring the per-user
    # weekly_enabled toggle (unlike the old no-op that re-sent a daily
    # digest on Mondays).
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        kwargs={"weekly": True},
        id="weekly_report",
        name="Weekly Report",
        replace_existing=True,
    )

    # Verify links daily at 2 AM
    scheduler.add_job(
        verify_job_links,
        CronTrigger(hour=2, minute=0),
        id="link_verification",
        name="Link Verification",
        replace_existing=True,
    )

    # Closing-soon alerts twice a day (UTC): once in the morning, once in
    # the evening — jobs expiring within 48h nudge each matching user once.
    scheduler.add_job(
        send_closing_soon_alerts,
        CronTrigger(hour=4, minute=30),
        id="closing_soon_alerts_morning",
        name="Closing Soon Alerts (morning)",
        replace_existing=True,
    )
    scheduler.add_job(
        send_closing_soon_alerts,
        CronTrigger(hour=12, minute=30),
        id="closing_soon_alerts_evening",
        name="Closing Soon Alerts (evening)",
        replace_existing=True,
    )

    # Deactivate expired jobs every hour
    scheduler.add_job(
        deactivate_expired_jobs,
        IntervalTrigger(hours=1),
        id="expire_jobs",
        name="Expire Jobs",
        replace_existing=True,
    )

    # Match-% progress snapshots daily at 23:30 UTC — one row per user per
    # day so the My Matches progress chart and the weekly trend line build
    # up over time without touching the digest path.
    scheduler.add_job(
        record_match_snapshots,
        CronTrigger(hour=23, minute=30),
        id="match_snapshots",
        name="Match % Snapshots",
        replace_existing=True,
    )

    # Interview reminders every 6 hours — nudges each enabled user 24-36h
    # before every scheduled interview, once per application.
    scheduler.add_job(
        send_interview_reminders,
        IntervalTrigger(hours=6),
        id="interview_reminders",
        name="Interview Reminders",
        replace_existing=True,
    )

    # Follow-up nudges daily — applications stuck in "applied" for 7+ days
    # get one nudge with a copy-paste follow-up message.
    scheduler.add_job(
        send_follow_up_nudges,
        CronTrigger(hour=9, minute=0),
        id="follow_up_nudges",
        name="Follow-up Nudges",
        replace_existing=True,
    )

    # Daily owner delivery summary at 14:30 UTC (20:00 IST) — after the
    # evening digest slot, so the owner sees what went out today without
    # logging in. On serverless the GitHub Actions cron hits the endpoint
    # instead.
    scheduler.add_job(
        send_daily_owner_summary,
        CronTrigger(hour=14, minute=30),
        id="daily_owner_summary",
        name="Daily Owner Summary",
        replace_existing=True,
    )

    return scheduler
