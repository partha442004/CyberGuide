"""
Applications API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.application import (
    ApplicationCreate,
    ApplicationListResponse,
    ApplicationMetrics,
    ApplicationResponse,
    ApplicationStatusUpdate,
    ApplicationUpdate,
)
from interntrack.database.session import get_db
from interntrack.services.application_service import ApplicationService

router = APIRouter()


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    status: str | None = None,
    user_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List applications, optionally filtered by status and/or user."""
    service = ApplicationService(db)

    if status:
        from interntrack.domain.enums import ApplicationStatus

        apps = await service.get_applications_by_status(
            ApplicationStatus(status),
            user_id=user_id,
        )
    elif user_id:
        # Per-user listing (all statuses).
        from interntrack.domain.models import Application

        result = await db.execute(
            select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        apps = list(result.scalars().all())
    else:
        apps = await service.app_repo.get_all(skip=skip, limit=limit)

    return ApplicationListResponse(applications=apps, total=len(apps))


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific application."""
    service = ApplicationService(db)
    app = await service.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.post("/", response_model=ApplicationResponse, status_code=201)
async def create_application(
    app_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new application (optionally owned by a user).

    When ``user_id`` is given and the user already applied to the job,
    returns the existing application (idempotent — no duplicate rows).
    """
    service = ApplicationService(db)
    existing = await service.get_application_for_job(
        app_data.job_id,
        user_id=app_data.user_id,
    )
    if existing:
        return existing
    return await service.create_application(app_data.job_id, user_id=app_data.user_id)


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    app_data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an application."""
    service = ApplicationService(db)
    updates = {k: v for k, v in app_data.model_dump().items() if v is not None}
    app = await service.app_repo.update(application_id, updates)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.delete("/{application_id}", status_code=204)
async def delete_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an application."""
    service = ApplicationService(db)
    deleted = await service.app_repo.delete(application_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_status(
    application_id: str,
    status_update: ApplicationStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update application status."""
    from interntrack.domain.enums import ApplicationStatus

    service = ApplicationService(db)
    app = await service.update_status(
        application_id,
        ApplicationStatus(status_update.status),
        status_update.notes,
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.get("/metrics/overview", response_model=ApplicationMetrics)
async def get_metrics(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get application metrics (optionally scoped to one user)."""
    service = ApplicationService(db)
    return await service.get_metrics(user_id=user_id)


@router.get("/timeline/recent")
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get application timeline (optionally scoped to one user)."""
    service = ApplicationService(db)
    return await service.get_application_timeline(days, user_id=user_id)
