"""
Dashboard API endpoints for aggregated data.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.services.application_service import ApplicationService
from interntrack.services.job_service import JobService

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard overview data.

    ``user_id`` scopes the application metrics to that user's own tracking
    (jobs remain global); without it the legacy global metrics are returned.
    """
    job_service = JobService(db)
    app_service = ApplicationService(db)

    job_stats = await job_service.get_job_statistics()
    app_metrics = await app_service.get_metrics(user_id=user_id)

    return {
        "jobs": job_stats,
        "applications": app_metrics,
    }


@router.get("/charts/job-types")
async def get_job_type_chart(
    db: AsyncSession = Depends(get_db),
):
    """Get job type distribution for charts."""
    service = JobService(db)
    stats = await service.get_job_statistics()
    return {"data": stats["job_types"]}


@router.get("/charts/application-timeline")
async def get_application_timeline_chart(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get application timeline for charts (optionally per user)."""
    service = ApplicationService(db)
    return {"data": await service.get_application_timeline(days=30, user_id=user_id)}


@router.get("/charts/top-companies")
async def get_top_companies_chart(
    db: AsyncSession = Depends(get_db),
):
    """Get top companies for charts."""
    service = JobService(db)
    stats = await service.get_job_statistics()
    return {"data": stats["top_companies"]}


@router.get("/charts/salary")
async def get_salary_chart(
    db: AsyncSession = Depends(get_db),
):
    """Get salary statistics for charts."""
    service = JobService(db)
    stats = await service.get_job_statistics()
    return {"data": stats["salary_stats"]}


@router.get("/recent-activity")
async def get_recent_activity(
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity feed."""
    job_service = JobService(db)
    app_service = ApplicationService(db)

    recent_jobs = await job_service.job_repo.get_recent_jobs(days=7)
    recent_apps = await app_service.app_repo.get_recent_applications(days=7)

    return {
        "recent_jobs": [
            {"id": j.id, "title": j.title, "company": j.company}
            for j in recent_jobs[:10]
        ],
        "recent_applications": [
            {"id": a.id, "status": a.status.value, "job_id": a.job_id}
            for a in recent_apps[:10]
        ],
    }
