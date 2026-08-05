"""
Reports API endpoints.
"""

import contextlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.report import ReportResponse
from interntrack.database.session import get_db
from interntrack.services.report_service import ReportService

router = APIRouter()


async def _send_alert_digest(
    db,
    prefs: dict,
    report: dict,
    weekly: bool = False,
    domains: list | None = None,
) -> dict:
    """Deliver a digest through the saved channels and record its history.

    Shared by the daily cron trigger and the Sunday weekly digest. Returns
    the per-channel delivery results (possibly empty when nothing was sent).
    ``domains`` overrides the saved preference filter (used by slot sends).
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_ALERT_USER,
        _deliver_alert,
        _record_alert_history,
    )
    from interntrack.services.notification_service import NotificationManager

    manager = NotificationManager(db)
    if not manager.get_configured_channels() or prefs.get("is_enabled") is False:
        return {}

    if domains is None:
        domains = prefs.get("domains") or None
    subject = "Weekly Digest" if weekly else "Daily Report"
    if domains:
        subject += f" ({', '.join(domains)})"
    channels = prefs.get("channels") or None
    results = await _deliver_alert(
        manager,
        channels,
        report,
        db,
        domains=domains,
        subject=subject,
        weekly=weekly,
    )
    await _record_alert_history(
        db,
        user_id=DEFAULT_ALERT_USER,
        subject=subject,
        channels=channels or list(results.keys()),
        domains=domains or [],
        job_count=len(report.get("new_jobs") or []),
        results=results,
    )
    return results


@router.get("/daily", response_model=ReportResponse)
async def get_daily_report(
    db: AsyncSession = Depends(get_db),
    slot: str | None = None,
):
    """Get daily report and send it to the configured notification channels.

    Vercel is serverless, so the APScheduler worker never runs there; the
    free GitHub Actions cron hits this endpoint to trigger the daily digest.
    Saved alert preferences (domains / channels / min match %) are applied;
    ``slot`` (morning / afternoon / evening) overrides the category filter
    with that slot's saved ``slot_domains`` when configured.
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_ALERT_USER,
        DEFAULT_SLOT_DOMAINS,
        _load_alert_preferences,
        _mark_alert_sent,
    )

    prefs = await _load_alert_preferences(db)
    domains = prefs.get("domains") or None
    if slot:
        # A configured slot wins; otherwise fall back to the slot default so
        # the three cron sends get distinct categories out of the box.
        slot_domains = prefs.get("slot_domains") or {}
        if slot in slot_domains and slot_domains[slot]:
            domains = slot_domains[slot]
        elif slot in DEFAULT_SLOT_DOMAINS:
            domains = DEFAULT_SLOT_DOMAINS[slot]
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
        await _send_alert_digest(db, prefs, report, domains=domains)

    return report


@router.get("/weekly-alert")
async def get_weekly_alert(
    db: AsyncSession = Depends(get_db),
):
    """Send the Sunday weekly digest: a recap of the last 7 days of jobs.

    Hits the same no-duplicate window as the daily digest but spans the
    whole week (``since = now - 7 days``), so every listing of the week is
    recapped in one email/Telegram digest on Sundays. Honors saved domains,
    channels and min match %, and records its send in history.
    """
    from interntrack.scheduler.jobs import _load_alert_preferences

    prefs = await _load_alert_preferences(db)
    if prefs.get("weekly_enabled") is False:
        return {
            "report_type": "weekly",
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {"new_jobs": 0, "skipped": "weekly digest disabled"},
            "new_jobs": [],
        }

    domains = prefs.get("domains") or None
    service = ReportService(db)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7),
    )
    report["report_type"] = "weekly"

    if not (report.get("new_jobs") or []):
        report["summary"] = {**report.get("summary", {}), "skipped": "no new jobs"}
        return report

    with contextlib.suppress(Exception):
        await _send_alert_digest(db, prefs, report, weekly=True)

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
