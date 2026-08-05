"""
Reports API endpoints.
"""

import contextlib

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.report import ReportResponse
from interntrack.database.session import get_db
from interntrack.services.report_service import ReportService

router = APIRouter()


@router.get("/daily", response_model=ReportResponse)
async def get_daily_report(
    db: AsyncSession = Depends(get_db),
):
    """Get daily report and send it to the configured notification channels.

    Vercel is serverless, so the APScheduler worker never runs there; the
    free GitHub Actions cron hits this endpoint to trigger the daily digest.
    Saved alert preferences (domains / channels / min match %) are applied.
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_ALERT_USER,
        _load_alert_preferences,
        _mark_alert_sent,
        _record_alert_history,
        build_daily_report_message,
    )
    from interntrack.services.notification_service import NotificationManager

    prefs = await _load_alert_preferences(db)
    domains = prefs.get("domains") or None
    service = ReportService(db)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=prefs.get("last_alert_at"),
    )

    # Advance the no-duplicates window regardless of whether anything new
    # was found, then skip the send when there are no new jobs.
    await _mark_alert_sent(db, DEFAULT_ALERT_USER)
    if not (report.get("new_jobs") or []):
        return report

    # Trigger the daily-digest notification (no-op when no channels
    # configured, or when the user has disabled alerts).
    with contextlib.suppress(Exception):
        manager = NotificationManager(db)
        if manager.get_configured_channels() and prefs.get("is_enabled") is not False:
            message = await build_daily_report_message(report, db, domains=domains)
            subject = "Daily Report"
            if domains:
                subject += f" ({', '.join(domains)})"
            channels = prefs.get("channels") or None
            if channels:
                results = await manager.notify(channels, message, subject=subject)
            else:
                results = await manager.notify_all(message, subject=subject)
            await _record_alert_history(
                db,
                user_id=DEFAULT_ALERT_USER,
                subject=subject,
                channels=channels or list(results.keys()),
                domains=domains or [],
                job_count=len(report.get("new_jobs") or []),
                results=results,
            )

    return report


@router.get("/weekly", response_model=ReportResponse)
async def get_weekly_report(
    db: AsyncSession = Depends(get_db),
):
    """Get weekly report."""
    service = ReportService(db)
    return await service.generate_weekly_report()


@router.get("/monthly", response_model=ReportResponse)
async def get_monthly_report(
    db: AsyncSession = Depends(get_db),
):
    """Get monthly report."""
    service = ReportService(db)
    return await service.generate_monthly_report()


@router.get("/{report_type}/html")
async def get_report_html(
    report_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Get report as HTML."""
    from fastapi.responses import HTMLResponse

    service = ReportService(db)

    if report_type == "daily":
        data = await service.generate_daily_report()
    elif report_type == "weekly":
        data = await service.generate_weekly_report()
    elif report_type == "monthly":
        data = await service.generate_monthly_report()
    else:
        return HTMLResponse("Invalid report type", status_code=400)

    html = await service.render_report(data)
    return HTMLResponse(html)
