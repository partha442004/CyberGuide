"""
Enhanced Application Tracker — track job application status with timeline.

Status flow: saved → applied → interview → assessment → offer → joined
Also: rejected, withdrawn
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Application, ApplicationStatus, Job

router = APIRouter()


class ApplicationUpdate(BaseModel):
    """Update application status."""

    status: str
    notes: str | None = None
    interview_at: str | None = None


class ApplicationCreate(BaseModel):
    """Create a new application."""

    job_id: str
    notes: str | None = None


# Status flow configuration
STATUS_FLOW = {
    "saved": {"next": ["applied", "withdrawn"], "icon": "💾", "color": "#94a3b8"},
    "applied": {
        "next": ["interview", "assessment", "rejected", "withdrawn"],
        "icon": "📤",
        "color": "#3b82f6",
    },
    "interview": {
        "next": ["assessment", "offer", "rejected", "withdrawn"],
        "icon": "🎤",
        "color": "#8b5cf6",
    },
    "assessment": {
        "next": ["interview", "offer", "rejected", "withdrawn"],
        "icon": "📝",
        "color": "#f59e0b",
    },
    "offer": {"next": ["joined", "withdrawn"], "icon": "🎉", "color": "#22c55e"},
    "joined": {"next": [], "icon": "✅", "color": "#10b981"},
    "rejected": {"next": [], "icon": "❌", "color": "#ef4444"},
    "withdrawn": {"next": [], "icon": "🚫", "color": "#64748b"},
}


@router.get("/")
async def list_applications(
    status: str | None = None,
    user_id: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all applications with optional status filter."""
    query = select(Application)
    if status:
        query = query.where(Application.status == status)
    if user_id:
        query = query.where(Application.user_id == user_id)
    query = query.order_by(Application.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    applications = result.scalars().all()

    # Get job details for each application
    apps_with_jobs = []
    for app in applications:
        job_result = await db.execute(select(Job).where(Job.id == app.job_id))
        job = job_result.scalar_one_or_none()

        apps_with_jobs.append(
            {
                "id": app.id,
                "job_id": app.job_id,
                "status": app.status.value if app.status else "saved",
                "status_icon": STATUS_FLOW.get(
                    app.status.value if app.status else "saved", {}
                ).get("icon", "❓"),
                "status_color": STATUS_FLOW.get(
                    app.status.value if app.status else "saved", {}
                ).get("color", "#94a3b8"),
                "created_at": str(app.created_at) if app.created_at else None,
                "applied_at": str(app.applied_at) if app.applied_at else None,
                "interview_at": str(app.interview_at) if app.interview_at else None,
                "notes": app.notes,
                "job": {
                    "id": job.id if job else None,
                    "title": job.title if job else "Unknown",
                    "company": job.company if job else "Unknown",
                    "location": job.location if job else None,
                    "url": job.url if job else None,
                    "source": job.source.value if job and job.source else "unknown",
                }
                if job
                else None,
            }
        )

    return {
        "applications": apps_with_jobs,
        "total": len(apps_with_jobs),
        "status_filter": status,
    }


@router.post("/")
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new application (save a job for tracking)."""
    # Check if job exists
    job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already applied
    existing = await db.execute(
        select(Application).where(Application.job_id == payload.job_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already tracking this job")

    app = Application(
        id=str(uuid4()),
        job_id=payload.job_id,
        status=ApplicationStatus.SAVED,
        notes=payload.notes,
    )
    db.add(app)
    await db.commit()

    return {
        "id": app.id,
        "status": "saved",
        "message": "Job saved for tracking",
    }


@router.put("/{application_id}")
async def update_application(
    application_id: str,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update application status with timeline tracking."""
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Validate status transition
    current_status = app.status.value if app.status else "saved"
    allowed_next = STATUS_FLOW.get(current_status, {}).get("next", [])
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{payload.status}'. Allowed: {allowed_next}",
        )

    # Update status
    new_status = ApplicationStatus(payload.status)
    old_status = app.status
    app.status = new_status

    # Set timestamps based on status
    if payload.status == "applied" and not app.applied_at:
        app.applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if payload.status == "interview" and payload.interview_at:
        app.interview_at = datetime.fromisoformat(
            payload.interview_at.replace("Z", "+00:00")
        ).replace(tzinfo=None)

    # Update notes
    if payload.notes:
        app.notes = payload.notes

    await db.commit()

    return {
        "id": app.id,
        "old_status": current_status,
        "new_status": payload.status,
        "status_icon": STATUS_FLOW.get(payload.status, {}).get("icon", "❓"),
        "message": f"Status updated: {current_status} → {payload.status}",
    }


@router.get("/stats")
async def application_stats(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get application statistics."""
    query = select(Application)
    if user_id:
        query = query.where(Application.user_id == user_id)

    result = await db.execute(query)
    applications = result.scalars().all()

    # Count by status
    status_counts = {}
    for app in applications:
        status = app.status.value if app.status else "saved"
        status_counts[status] = status_counts.get(status, 0) + 1

    # Calculate conversion rates
    total = len(applications)
    applied = status_counts.get("applied", 0)
    interviews = status_counts.get("interview", 0)
    offers = status_counts.get("offer", 0)

    return {
        "total": total,
        "by_status": status_counts,
        "conversion_rates": {
            "applied_rate": round(applied / max(total, 1) * 100, 1),
            "interview_rate": round(interviews / max(applied, 1) * 100, 1),
            "offer_rate": round(offers / max(interviews, 1) * 100, 1),
        },
        "pipeline": {
            "saved": status_counts.get("saved", 0),
            "applied": applied,
            "interview": interviews,
            "assessment": status_counts.get("assessment", 0),
            "offer": offers,
            "joined": status_counts.get("joined", 0),
            "rejected": status_counts.get("rejected", 0),
        },
    }


@router.get("/timeline/{application_id}")
async def application_timeline(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the timeline of status changes for an application."""
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Build timeline from status history
    timeline = []
    current_status = app.status.value if app.status else "saved"

    # Add creation event
    timeline.append(
        {
            "status": "created",
            "icon": "🆕",
            "timestamp": str(app.created_at) if app.created_at else None,
            "note": "Job saved for tracking",
        }
    )

    # Add status transitions
    if app.applied_at:
        timeline.append(
            {
                "status": "applied",
                "icon": "📤",
                "timestamp": str(app.applied_at),
                "note": "Application submitted",
            }
        )

    if app.interview_at:
        timeline.append(
            {
                "status": "interview",
                "icon": "🎤",
                "timestamp": str(app.interview_at),
                "note": "Interview scheduled",
            }
        )

    # Add current status
    status_info = STATUS_FLOW.get(current_status, {})
    timeline.append(
        {
            "status": current_status,
            "icon": status_info.get("icon", "❓"),
            "timestamp": str(app.updated_at) if app.updated_at else None,
            "note": app.notes or f"Status: {current_status}",
        }
    )

    return {
        "application_id": application_id,
        "current_status": current_status,
        "timeline": timeline,
    }
