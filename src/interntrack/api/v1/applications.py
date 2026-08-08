"""
Applications API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.application import (
    ApplicationCreate,
    ApplicationHistoryItem,
    ApplicationHistoryResponse,
    ApplicationListResponse,
    ApplicationMetrics,
    ApplicationResponse,
    ApplicationStatusUpdate,
    ApplicationUpdate,
    FollowUpItem,
    FollowUpsResponse,
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


@router.get("/follow-ups", response_model=FollowUpsResponse)
async def get_follow_ups(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Applications that need a follow-up nudge, most urgent first.

    These are the same applications the daily email/Telegram digest
    reminds the user about: ``applied`` / ``interview`` applications that
    haven't been marked as followed up yet. The dashboard surfaces them
    so the user can act immediately instead of waiting for the next
    digest — and can mark them followed up right there.

    ``days_since`` is how long the application has been sitting (based on
    ``applied_at``, falling back to ``created_at``) so urgency is clear
    at a glance.
    """
    from interntrack.domain.models import Job
    from interntrack.utils.helpers import utcnow

    service = ApplicationService(db)
    pending = await service.app_repo.get_pending_reminders(user_id=user_id)

    items: list[FollowUpItem] = []
    if not pending:
        return FollowUpsResponse(follow_ups=items)

    # Batch-load job titles/companies/urls for enrichment (one query).
    job_ids = [app.job_id for app in pending]
    job_rows = await db.execute(
        select(Job.id, Job.title, Job.company, Job.url).where(Job.id.in_(job_ids))
    )
    jobs_by_id = {row[0]: row for row in job_rows.all()}

    now = utcnow()
    for app in pending:
        row = jobs_by_id.get(app.job_id)
        # applied_at/created_at are coerced to naive UTC by the model
        # validators, matching utcnow() — the subtraction is safe.
        base_time = app.applied_at or app.created_at
        days_since = (now - base_time).days if base_time else 0
        items.append(
            FollowUpItem(
                application_id=app.id,
                job_id=app.job_id,
                job_title=row[1] if row else None,
                company=row[2] if row else None,
                job_url=row[3] if row else None,
                # Enum member -> value (native_enum=False columns).
                status=str(getattr(app.status, "value", app.status)),
                applied_at=app.applied_at,
                days_since=max(0, days_since),
            )
        )
    items.sort(key=lambda i: i.days_since, reverse=True)
    return FollowUpsResponse(follow_ups=items)


@router.post("/{application_id}/reminded", status_code=200)
async def mark_application_reminded(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark an application as followed up.

    Stops the daily digests from nudging this application again (the
    same mechanism the digest uses after a successful send), and removes
    it from the dashboard's Follow-ups list.
    """
    from interntrack.domain.models import Application

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    # Same flag the digest sets after a successful send — stops future nudges.
    application.reminded = True  # type: ignore[assignment]
    await db.flush()
    return {"status": "ok"}


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


@router.get("/{application_id}/history", response_model=ApplicationHistoryResponse)
async def get_application_history(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get an application's status-change timeline (oldest first).

    Every status change made through the API (or the dashboard's
    Applications page) is recorded in ``application_status_history``;
    this endpoint exposes that audit trail so users can see exactly how
    an application progressed (saved → applied → interview → ...) and
    when. Returns an empty list for applications that never changed
    status.
    """
    from interntrack.domain.models import Application, ApplicationStatusHistory

    app_result = await db.execute(
        select(Application.id).where(Application.id == application_id)
    )
    if app_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Application not found")

    rows = await db.execute(
        select(
            ApplicationStatusHistory.new_status,
            ApplicationStatusHistory.changed_at,
            ApplicationStatusHistory.notes,
        )
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(
            ApplicationStatusHistory.changed_at.asc(),
            ApplicationStatusHistory.new_status.asc(),
        )
    )
    history = [
        ApplicationHistoryItem(
            # SQLAlchemy returns the enum member (``ApplicationStatus``) for
            # native_enum=False columns — coerce to its string value.
            status=str(getattr(status, "value", status)),
            changed_at=changed_at,
            notes=notes,
        )
        for status, changed_at, notes in rows.all()
    ]
    return ApplicationHistoryResponse(application_id=application_id, history=history)


@router.get("/timeline/recent")
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get application timeline (optionally scoped to one user)."""
    service = ApplicationService(db)
    return await service.get_application_timeline(days, user_id=user_id)
