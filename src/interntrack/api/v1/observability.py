"""
User-facing observability endpoints.

Provides discovery history, scraper health dashboard, and match feedback.
"""

from datetime import UTC

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.deps import require_cron_secret
from interntrack.database.session import get_db
from interntrack.domain.models import Job, NotificationHistory

# These endpoints expose operational details (scraper yields, discovery
# history, member match trends) — useful to the owner, a recon gift to
# strangers. Guarded like the other cron/ops endpoints; the Streamlit
# dashboard sends the same X-Cron-Secret header.
router = APIRouter(dependencies=[Depends(require_cron_secret)])


@router.get("/discovery-history")
async def discovery_history(
    days: int = Query(default=7, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Get discovery history for the last N days.

    Shows how many jobs were found per day, per source, and per domain.
    """
    from datetime import datetime, timedelta

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

    # Jobs discovered in the period
    query = select(Job).where(Job.created_at >= cutoff).order_by(Job.created_at.desc())
    result = await db.execute(query)
    recent_jobs = result.scalars().all()

    # Group by day
    by_day: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_company: dict[str, int] = {}

    for job in recent_jobs:
        day = str(job.created_at.date()) if job.created_at else "unknown"
        by_day[day] = by_day.get(day, 0) + 1

        source = job.source.value if job.source else "unknown"
        by_source[source] = by_source.get(source, 0) + 1

        company_key = str(job.company)
        by_company[company_key] = by_company.get(company_key, 0) + 1

    top_companies = sorted(by_company.items(), key=lambda x: x[1], reverse=True)[:10]

    # Notification history
    notif_query = (
        select(NotificationHistory)
        .where(NotificationHistory.created_at >= cutoff)
        .order_by(NotificationHistory.created_at.desc())
        .limit(20)
    )
    notif_result = await db.execute(notif_query)
    notifications = notif_result.scalars().all()

    return {
        "period_days": days,
        "summary": {
            "total_discovered": len(recent_jobs),
            "unique_companies": len(by_company),
            "avg_per_day": round(len(recent_jobs) / max(days, 1), 1),
        },
        "by_day": [{"date": d, "count": c} for d, c in sorted(by_day.items())],
        "by_source": [
            {"source": s, "count": c}
            for s, c in sorted(by_source.items(), key=lambda x: x[1], reverse=True)
        ],
        "top_companies": [{"company": c, "count": n} for c, n in top_companies],
        "recent_notifications": [
            {
                "id": n.id,
                "subject": n.subject,
                "channels": n.channels,
                "domains": n.domains,
                "job_count": n.job_count,
                "created_at": str(n.created_at) if n.created_at else None,
            }
            for n in notifications
        ],
    }


@router.get("/scraper-health")
async def scraper_health(
    db: AsyncSession = Depends(get_db),
):
    """Get scraper health status — which sources are working, which are blocked."""
    from datetime import datetime, timedelta

    cutoff_7d = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    cutoff_24h = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)

    # All sources
    query = select(Job.source, func.count(Job.id)).group_by(Job.source)
    result = await db.execute(query)
    source_totals = {str(row[0]): row[1] for row in result.all()}

    # Recent 24h
    query_24h = (
        select(Job.source, func.count(Job.id))
        .where(Job.created_at >= cutoff_24h)
        .group_by(Job.source)
    )
    result_24h = await db.execute(query_24h)
    source_24h = {str(row[0]): row[1] for row in result_24h.all()}

    # Recent 7d
    query_7d = (
        select(Job.source, func.count(Job.id))
        .where(Job.created_at >= cutoff_7d)
        .group_by(Job.source)
    )
    result_7d = await db.execute(query_7d)
    source_7d = {str(row[0]): row[1] for row in result_7d.all()}

    # Build health report
    all_sources = (
        set(source_totals.keys()) | set(source_24h.keys()) | set(source_7d.keys())
    )
    sources = []
    for src in sorted(all_sources):
        total = source_totals.get(src, 0)
        count_24h = source_24h.get(src, 0)
        count_7d = source_7d.get(src, 0)
        avg_daily_7d = round(count_7d / 7, 1)

        # Determine health status
        if count_24h > 0:
            status = "healthy"
            status_color = "#22c55e"
        elif count_7d > 0:
            status = "degraded"
            status_color = "#f59e0b"
        elif total > 0:
            status = "stale"
            status_color = "#ef4444"
        else:
            status = "unknown"
            status_color = "#94a3b8"

        sources.append(
            {
                "source": src,
                "status": status,
                "status_color": status_color,
                "total_jobs": total,
                "jobs_24h": count_24h,
                "jobs_7d": count_7d,
                "avg_daily_7d": avg_daily_7d,
            }
        )

    sources.sort(key=lambda s: s["jobs_24h"], reverse=True)

    healthy = sum(1 for s in sources if s["status"] == "healthy")
    total = len(sources)

    return {
        "summary": {
            "total_sources": total,
            "healthy": healthy,
            "degraded": sum(1 for s in sources if s["status"] == "degraded"),
            "stale": sum(1 for s in sources if s["status"] == "stale"),
            "health_pct": round(healthy / max(total, 1) * 100, 1),
        },
        "sources": sources,
    }


@router.post("/reliability-digest")
async def reliability_digest(
    db: AsyncSession = Depends(get_db),
):
    """Send the owner a reliability digest and return it as JSON.

    Called weekly (and ad-hoc) by a cron-guarded GitHub Actions workflow.
    Sections:
    - uptime: UptimeRobot 7-day availability when ``UPTIMEROBOT_API_KEY``
      is configured (skipped otherwise — the free key is added in Vercel).
    - discovery: jobs found per source over the last 7 days (from the DB).
    - delivery: per-channel notification counters over the last 7 days.
    Also flips the owner's alert preferences to fresher-only (domains
    ``security``, ``cloud``; experience levels ``fresher``, ``intern``)
    — idempotent, so it is safe to call every week.
    """
    import logging

    import httpx

    from interntrack.config import get_settings

    settings = get_settings()

    # ── Owner preferences → fresher-only (idempotent) ─────────────────
    from interntrack.api.v1.users import _new_access_token
    from interntrack.domain.models import AlertPreferences, User

    owner_email = settings.smtp_user or settings.effective_email_from
    result = await db.execute(select(User).where(User.email == owner_email))
    owner = result.scalars().first()
    prefs_applied: dict = {"owner_found": bool(owner)}
    if owner is not None:
        fresh = ["security", "cloud"]
        prefs_result = await db.execute(
            select(AlertPreferences).where(AlertPreferences.user_id == owner.id)
        )
        pref: AlertPreferences | None = prefs_result.scalars().first()
        if pref is None:
            pref = AlertPreferences(user_id=owner.id, is_enabled=True)
            db.add(pref)
        pref.domains = fresh  # type: ignore[assignment]
        pref.experience_levels = ["fresher", "intern"]  # type: ignore[assignment]
        if not owner.access_token:
            owner.access_token = _new_access_token()  # type: ignore[assignment]
        await db.commit()
        prefs_applied.update(
            {
                "domains": fresh,
                "experience_levels": ["fresher", "intern"],
                "access_token_issued": True,
            }
        )

    # ── UptimeRobot uptime (last 7 days) ──────────────────────────────
    uptime: dict = {"status": "skipped", "reason": "UPTIMEROBOT_API_KEY not set"}
    if settings.uptimerobot_api_key:
        try:
            resp = await httpx.AsyncClient(timeout=15).post(
                "https://api.uptimerobot.com/v2/getMonitors",
                data={
                    "api_key": settings.uptimerobot_api_key,
                    "monitors": "1-",
                    "custom_uptime_ratios": "7",
                },
            )
            monitors = (resp.json() or {}).get("monitors") or []
            uptime = {
                "status": "ok",
                "monitors": [
                    {
                        "name": m.get("friendly_name"),
                        "uptime_7d": m.get("custom_uptime_ratio"),
                        "state": m.get("status"),
                    }
                    for m in monitors
                ],
            }
        except Exception:  # noqa: BLE001 — digest must not fail wholesale
            logging.getLogger(__name__).debug("uptime section failed", exc_info=True)
            uptime = {"status": "error"}

    # ── Discovery stats (last 7 days, per source) ─────────────────────
    from datetime import datetime, timedelta

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)
    discovery: dict[str, int] = {}
    try:
        source_rows = await db.execute(
            select(Job.source, func.count(Job.id))
            .where(Job.created_at >= cutoff)
            .group_by(Job.source)
        )
        discovery = {str(src): count for src, count in source_rows.all()}
    except Exception:  # noqa: BLE001 — digest must not fail wholesale
        logging.getLogger(__name__).debug("discovery stats failed", exc_info=True)

    # ── Delivery stats (last 7 days, per channel) ─────────────────────
    # Aggregated in Python: ``channels`` is a JSON column and Postgres
    # cannot GROUP BY JSON without a cast, which broke this in production.
    delivery: dict[str, int] = {}
    try:
        channel_rows = await db.execute(
            select(NotificationHistory.channels).where(
                NotificationHistory.created_at >= cutoff
            )
        )
        for (chans,) in channel_rows.all():
            key = ",".join(chans) if isinstance(chans, list) else str(chans)
            delivery[key] = delivery.get(key, 0) + 1
    except Exception:  # noqa: BLE001 — digest must not fail wholesale
        logging.getLogger(__name__).debug("delivery stats failed", exc_info=True)

    # ── Self-check: prove the Telegram channel still works ─────────────
    telegram_self_check = "skipped: not configured"
    try:
        from interntrack.services.notification_service import NotificationManager

        manager = NotificationManager(db)
        if "telegram" in manager.get_configured_channels():
            ok = await manager.notify(
                ["telegram"],
                "✅ Reliability digest self-check: Telegram delivery works.",
                subject="InternTrack: reliability self-check",
            )
            telegram_self_check = "sent" if ok else "failed"
    except Exception:  # noqa: BLE001 — digest must not fail wholesale
        telegram_self_check = "error"

    # ── Deliver the digest to the owner (email + Telegram) ─────────────
    lines = [f"🛡 InternTrack reliability digest — week of {cutoff:%d %b}", ""]
    if uptime.get("status") == "ok":
        for monitor in uptime.get("monitors", []):
            lines.append(
                f"• {monitor.get('name')}: {monitor.get('uptime_7d')}% uptime (7d)"
            )
    else:
        lines.append(
            f"• Uptime: {uptime.get('status')} ({uptime.get('reason', 'n/a')})"
        )
    total_jobs = sum(discovery.values())
    top_sources = sorted(discovery.items(), key=lambda kv: kv[1], reverse=True)[:5]
    sources_line = ", ".join(f"{src} {count}" for src, count in top_sources) or "none"
    lines.append(f"• Discovery 7d: {total_jobs} jobs ({sources_line})")
    lines.append(f"• Notification sends 7d: {sum(delivery.values())}")
    lines.append(f"• Telegram self-check: {telegram_self_check}")
    lines.append("")
    lines.append("Owner prefs are fresher-only (security, cloud).")
    delivered_to: list[str] = []
    try:
        from interntrack.services.notification_service import NotificationManager

        manager = NotificationManager(db)
        configured = manager.get_configured_channels()
        ok = await manager.notify(
            configured,
            "\n".join(lines),
            subject="InternTrack: weekly reliability digest",
        )
        if ok:
            delivered_to = configured
    except Exception:  # noqa: BLE001 — digest must not fail wholesale
        logging.getLogger(__name__).debug(
            "reliability digest delivery failed", exc_info=True
        )

    return {
        "period_days": 7,
        "owner_prefs": prefs_applied,
        "uptime": uptime,
        "discovery_7d": discovery,
        "delivery_7d": delivery,
        "telegram_self_check": telegram_self_check,
        "delivered_to": delivered_to,
        "digest": "\n".join(lines),
    }


@router.get("/debug/sentry-test")
async def sentry_test():
    """Fire a deliberate unhandled exception to verify Sentry delivery.

    Exists so the deployment's error pipeline can be proven end-to-end: if the
    ``SENTRY_DSN`` is configured, this 500 is captured by the Sentry FastAPI
    integration and appears as an issue in the ``cyberguide-api`` project a
    few seconds later. Guarded by the router-level cron-secret dependency like
    the rest of the observability routes; also refuses to run when Sentry is
    not initialized, so the endpoint is inert rather than a 500 noise source.
    """
    try:
        import sentry_sdk
    except ImportError:
        # SDK not installed on this environment — treat as uninitialized.
        sentry_sdk = None  # type: ignore[assignment]
    # get_client() never returns None on SDK 2.x (it hands back a no-op
    # client), so probe the DSN: it is only set when init() received a
    # real one, i.e. exactly when events can actually be delivered.
    if not sentry_sdk or not getattr(sentry_sdk.get_client(), "dsn", None):
        return {
            "status": "skipped",
            "reason": "Sentry is not initialized on this deployment "
            "(SENTRY_DSN not set)",
        }
    raise RuntimeError(
        "Sentry delivery test from cyberguide-api /debug/sentry-test — safe to resolve"
    )


@router.post("/feedback")
async def match_feedback(
    job_id: str,
    rating: int = Query(ge=1, le=5, description="1=not relevant, 5=very relevant"),
    comment: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Submit match quality feedback to improve scoring over time."""
    from uuid import uuid4

    from interntrack.domain.models import ActivityLog

    log = ActivityLog(
        id=str(uuid4()),
        action="match_feedback",
        entity_type="job",
        entity_id=job_id,
        details={"rating": rating, "comment": comment},
    )
    db.add(log)
    await db.commit()

    return {
        "status": "recorded",
        "job_id": job_id,
        "rating": rating,
        "message": "Thanks! Your feedback helps improve job matching.",
    }
