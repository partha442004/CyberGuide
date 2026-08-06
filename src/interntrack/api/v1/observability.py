"""
User-facing observability endpoints.

Provides discovery history, scraper health dashboard, and match feedback.
"""

from datetime import UTC

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Job, NotificationHistory

router = APIRouter()


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
