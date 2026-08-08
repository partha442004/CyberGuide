"""
Reports API endpoints.
"""

import contextlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.report import ReportResponse
from interntrack.database.session import get_db
from interntrack.services.application_service import ApplicationService
from interntrack.services.report_service import ReportService

router = APIRouter()


async def _send_alert_digest(
    db,
    prefs: dict,
    report: dict,
    weekly: bool = False,
    domains: list | None = None,
    user_id: str | None = None,
    user=None,
) -> dict:
    """Deliver a digest through the saved channels and record its history.

    Shared by the daily cron trigger and the Sunday weekly digest. Returns
    the per-channel delivery results (possibly empty when nothing was sent).
    ``domains`` overrides the saved preference filter (used by slot sends).
    ``user`` personalizes delivery (email / Telegram) and match %.
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_ALERT_USER,
        _alerts_paused,
        _deliver_alert,
        _record_alert_history,
    )
    from interntrack.services.notification_service import NotificationManager

    manager = NotificationManager(db)
    if (
        not manager.get_configured_channels()
        or prefs.get("is_enabled") is False
        or _alerts_paused(prefs)
    ):
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
        user=user,
    )
    await _record_alert_history(
        db,
        user_id=user_id or DEFAULT_ALERT_USER,
        subject=subject,
        channels=channels or list(results.keys()),
        domains=domains or [],
        job_count=len(report.get("new_jobs") or []),
        results=results,
    )
    # Successfully-reminded applications stop being nudged. Only mark when at
    # least one channel actually delivered (a dict like {"telegram": False} is
    # truthy but means nothing was sent).
    if results and any(results.values()):
        for item in report.get("follow_up") or []:
            app_id = item.get("application_id")
            if app_id:
                with contextlib.suppress(Exception):
                    await ApplicationService(db).mark_reminded(app_id)
    return results


async def _load_digest_targets(db) -> list[dict]:
    """Enabled alert targets, or the legacy single-user target.

    Returns ``[{user_id, prefs, user}]`` — one entry per registered account
    with alerts enabled, or a single legacy ``user1`` target when no accounts
    exist yet (pre-account deployments behave exactly as before).
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_ALERT_USER,
        _enabled_alert_targets,
        _load_alert_preferences,
    )

    targets = await _enabled_alert_targets(db)
    if not targets:
        targets = [
            {
                "user_id": DEFAULT_ALERT_USER,
                "prefs": await _load_alert_preferences(db),
                "user": None,
            }
        ]
    return targets


async def _top_engaged_jobs(db, days: int = 7, limit: int = 5) -> list[dict]:
    """Most-engaged jobs of the last N days, for the weekly recap.

    Ranks jobs by the same engagement formula as 🔥 Trending (3 per
    application + 2 per bookmark + 0.5 per view) so the weekly digest can
    lead with what people actually applied to / saved / opened. Returns
    plain dicts (title / company / url / location / counts / score) —
    never raises, returns [] on any error so the weekly digest is never
    broken by a stats failure.
    """
    try:
        from datetime import timedelta

        from sqlalchemy import func, select

        from interntrack.domain.models import Application, Bookmark, Job
        from interntrack.utils.helpers import utcnow

        cutoff = utcnow() - timedelta(days=days)
        rows = (
            (
                await db.execute(
                    select(Job).where(
                        Job.is_active.is_(True),
                        Job.created_at >= cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return []
        job_ids = [j.id for j in rows]
        app_rows = (
            await db.execute(
                select(Application.job_id, func.count(Application.id))
                .where(Application.job_id.in_(job_ids))
                .group_by(Application.job_id)
            )
        ).all()
        app_counts: dict[str, int] = {str(rid): int(cnt) for rid, cnt in app_rows}
        bm_rows = (
            await db.execute(
                select(Bookmark.item_id, func.count(Bookmark.id))
                .where(
                    Bookmark.item_type == "job",
                    Bookmark.item_id.in_(job_ids),
                )
                .group_by(Bookmark.item_id)
            )
        ).all()
        bm_counts: dict[str, int] = {str(iid): int(cnt) for iid, cnt in bm_rows}

        scored = []
        for job in rows:
            views = int(job.view_count or 0)
            apps = int(app_counts.get(str(job.id), 0))
            bms = int(bm_counts.get(str(job.id), 0))
            score = apps * 3 + bms * 2 + views * 0.5
            if score <= 0:
                continue
            scored.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "views": views,
                    "applications": apps,
                    "bookmarks": bms,
                    "engagement_score": round(score, 1),
                }
            )
        scored.sort(key=lambda item: item["engagement_score"], reverse=True)
        return scored[:limit]
    except Exception:  # noqa: BLE001 - never break the weekly digest
        return []


async def _empty_report(report_type: str, note: str) -> dict:
    """A minimal report dict for when nothing could be sent."""
    return {
        "report_type": report_type,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"new_jobs": 0, "skipped": note},
        "new_jobs": [],
    }


@router.get("/daily", response_model=ReportResponse)
async def get_daily_report(
    db: AsyncSession = Depends(get_db),
    slot: str | None = None,
    preview: bool = False,
):
    """Get daily report and send it to the configured notification channels.

    Vercel is serverless, so the APScheduler worker never runs there; the
    free GitHub Actions cron hits this endpoint to trigger the daily digest.
    Saved alert preferences (domains / channels / min match %) are applied;
    ``slot`` (morning / afternoon / evening) overrides the category filter
    with that slot's saved ``slot_domains`` when configured. ``preview``
    builds the report WITHOUT sending it or advancing the no-duplicates
    window — the dashboard uses it to show exactly what today's digest
    contains before it's delivered.
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_SLOT_DOMAINS,
        _alerts_paused,
        _mark_alert_sent,
    )

    targets = await _load_digest_targets(db)
    last_report = None
    for target in targets:
        prefs = target["prefs"]
        if prefs.get("is_enabled") is False or _alerts_paused(prefs):
            continue
        domains = prefs.get("domains") or None
        if slot:
            # A configured slot wins; otherwise fall back to the slot
            # default so the three cron sends get distinct categories.
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
            user_id=target["user_id"],
        )

        # Preview mode builds the digest without delivering it and without
        # advancing the no-duplicates window (so previewing never causes a
        # job to be skipped from the real next send).
        if preview:
            last_report = report
            continue
        # Advance the no-duplicates window regardless of whether anything
        # new was found, then skip the send when there are no new jobs.
        await _mark_alert_sent(db, target["user_id"])
        if report.get("new_jobs") or []:
            # Trigger the daily-digest notification (no-op when no channels
            # configured, or when the user has disabled alerts).
            with contextlib.suppress(Exception):
                await _send_alert_digest(
                    db,
                    prefs,
                    report,
                    domains=domains,
                    user_id=target["user_id"],
                    user=target["user"],
                )
        last_report = report

    if last_report is None:
        return await _empty_report("daily", "no alerts enabled")
    return last_report


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
    from interntrack.scheduler.jobs import _alerts_paused

    targets = await _load_digest_targets(db)
    last_report = None
    sent_any = False
    for target in targets:
        prefs = target["prefs"]
        if prefs.get("weekly_enabled") is False or _alerts_paused(prefs):
            continue
        domains = prefs.get("domains") or None
        service = ReportService(db)
        report = await service.generate_daily_report(
            domains=domains,
            min_match_score=prefs.get("min_match_score"),
            since=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7),
        )
        report["report_type"] = "weekly"
        # Attach the week's most-engaged jobs (apps + bookmarks + views)
        # so the email / Telegram recap can lead with real activity.
        report["top_engaged"] = await _top_engaged_jobs(db)

        if report.get("new_jobs") or []:
            with contextlib.suppress(Exception):
                await _send_alert_digest(
                    db,
                    prefs,
                    report,
                    weekly=True,
                    user_id=target["user_id"],
                    user=target["user"],
                )
            sent_any = True
        last_report = report

    if last_report is None:
        return await _empty_report("weekly", "weekly digest disabled")
    if not sent_any:
        last_report["summary"] = {
            **last_report.get("summary", {}),
            "skipped": "no new jobs",
        }
    return last_report


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
