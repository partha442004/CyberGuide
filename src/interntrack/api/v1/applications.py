"""
Applications API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all applications."""
    service = ApplicationService(db)

    if status:
        from interntrack.domain.enums import ApplicationStatus

        apps = await service.get_applications_by_status(ApplicationStatus(status))
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
    """Create a new application."""
    service = ApplicationService(db)
    app = await service.create_application(app_data.job_id)
    return app


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
    db: AsyncSession = Depends(get_db),
):
    """Get application metrics."""
    service = ApplicationService(db)
    return await service.get_metrics()


@router.get("/timeline/recent")
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get application timeline."""
    service = ApplicationService(db)
    return await service.get_application_timeline(days)
