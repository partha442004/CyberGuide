"""
Weekly Digest API — Sunday summary with trends, new companies, top skills.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Application, Job

router = APIRouter()


@router.get("/summary")
async def weekly_summary(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get weekly summary with trends compared to last week."""
    now = datetime.now(UTC).replace(tzinfo=None)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # This week's jobs
    query_this = select(func.count(Job.id)).where(Job.created_at >= week_ago)
    this_week_jobs = (await db.execute(query_this)).scalar() or 0

    # Last week's jobs
    query_last = select(func.count(Job.id)).where(
        Job.created_at >= two_weeks_ago, Job.created_at < week_ago
    )
    last_week_jobs = (await db.execute(query_last)).scalar() or 0

    # Applications this week
    query_apps = select(func.count(Application.id)).where(
        Application.created_at >= week_ago
    )
    if user_id:
        query_apps = query_apps.where(Application.user_id == user_id)
    apps_this_week = (await db.execute(query_apps)).scalar() or 0

    # New companies this week
    query_companies = select(Job.company).where(Job.created_at >= week_ago).distinct()
    new_companies_result = await db.execute(query_companies)
    new_companies = [r[0] for r in new_companies_result.all()]

    # Top skills in demand this week
    query_jobs = select(Job).where(Job.created_at >= week_ago)
    jobs_result = await db.execute(query_jobs)
    recent_jobs = jobs_result.scalars().all()

    skill_counts: dict[str, int] = {}
    for job in recent_jobs:
        if job.tags:
            for tag in list(job.tags):
                skill_counts[tag] = skill_counts.get(tag, 0) + 1

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Trend calculation
    if last_week_jobs > 0:
        trend_pct = round((this_week_jobs - last_week_jobs) / last_week_jobs * 100, 1)
        trend = "up" if trend_pct > 0 else "down" if trend_pct < 0 else "flat"
    else:
        trend_pct = 0
        trend = "new"

    return {
        "period": {
            "start": str(week_ago.date()),
            "end": str(now.date()),
        },
        "jobs": {
            "this_week": this_week_jobs,
            "last_week": last_week_jobs,
            "trend": trend,
            "trend_pct": trend_pct,
        },
        "applications": {
            "this_week": apps_this_week,
        },
        "new_companies": new_companies[:10],
        "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
        "highlights": [
            f"📊 {this_week_jobs} new jobs discovered this week"
            if this_week_jobs
            else None,
            f"🏢 {len(new_companies)} new companies added" if new_companies else None,
            f"🎯 {apps_this_week} applications submitted" if apps_this_week else None,
            f"📈 Job market {trend} {abs(trend_pct)}% vs last week"
            if trend != "new"
            else None,
        ],
    }


@router.get("/trends")
async def job_trends(
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get job discovery trends over time."""
    now = datetime.now(UTC).replace(tzinfo=None)
    start = now - timedelta(days=days)

    query = select(Job).where(Job.created_at >= start)
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Group by day
    by_day: dict[str, int] = {}
    for job in jobs:
        day = str(job.created_at.date()) if job.created_at else "unknown"
        by_day[day] = by_day.get(day, 0) + 1

    # Group by source
    by_source: dict[str, int] = {}
    for job in jobs:
        source = job.source.value if job.source else "unknown"
        by_source[source] = by_source.get(source, 0) + 1

    # Group by domain
    from interntrack.api.v1.salary_insights import _classify_domain

    by_domain: dict[str, int] = {}
    for job in jobs:
        domain = _classify_domain(str(job.title), str(job.description or ""))
        by_domain[domain] = by_domain.get(domain, 0) + 1

    return {
        "period_days": days,
        "total_jobs": len(jobs),
        "by_day": [{"date": d, "count": c} for d, c in sorted(by_day.items())],
        "by_source": [
            {"source": s, "count": c}
            for s, c in sorted(by_source.items(), key=lambda x: x[1], reverse=True)
        ],
        "by_domain": [
            {"domain": d, "count": c}
            for d, c in sorted(by_domain.items(), key=lambda x: x[1], reverse=True)
        ],
    }
