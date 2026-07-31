"""
Applications API Router

Endpoints for application tracking and management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.dependencies import get_session, get_application_repository
from cybershield.repositories.application_repository import ApplicationRepository
from cybershield.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationStatusUpdate,
    ApplicationMetrics,
)
from cybershield.domain.models import ApplicationStatus

router = APIRouter()


@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    user_id: str = Query(...),
    status: Optional[ApplicationStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """List applications for a user with optional status filter."""
    applications = await repo.get_user_applications(
        user_id=user_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return applications


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: str,
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """Get application by ID with job details."""
    application = await repo.get_with_job(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.post("/", response_model=ApplicationResponse, status_code=201)
async def create_application(
    application_data: ApplicationCreate,
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """Create a new application record."""
    application = await repo.create(application_data.model_dump())
    return application


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: str,
    status_update: ApplicationStatusUpdate,
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """Update application status with history tracking."""
    application = await repo.update_status(
        application_id=application_id,
        new_status=status_update.status,
        notes=status_update.notes,
    )
    return application


@router.get("/{application_id}/history", response_model=List[dict])
async def get_application_history(
    application_id: str,
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """Get status change history for an application."""
    history = await repo.get_status_history(application_id)
    return history


@router.get("/user/{user_id}/metrics", response_model=ApplicationMetrics)
async def get_user_metrics(
    user_id: str,
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """Get application metrics for a user."""
    metrics = await repo.get_application_metrics(user_id)
    return metrics


@router.get("/user/{user_id}/deadlines", response_model=List[ApplicationResponse])
async def get_upcoming_deadlines(
    user_id: str,
    days: int = Query(7, ge=1, le=30),
    repo: ApplicationRepository = Depends(get_application_repository),
):
    """Get applications with upcoming deadlines."""
    applications = await repo.get_upcoming_deadlines(user_id=user_id, days=days)
    return applications
