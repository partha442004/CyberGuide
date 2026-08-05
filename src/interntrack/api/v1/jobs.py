"""
Jobs API endpoints.
"""

import contextlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.job import (
    JobCreate,
    JobListResponse,
    JobResponse,
    JobSearchRequest,
    JobStatistics,
    JobUpdate,
)
from interntrack.database.session import get_db
from interntrack.domain.exceptions import DuplicateJobError
from interntrack.services.job_service import JobService

router = APIRouter()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    job_type: str | None = None,
    is_remote: bool | None = None,
    company: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List jobs with filters."""
    from interntrack.domain.enums import JobType

    service = JobService(db)
    parsed_job_type = None
    if job_type:
        try:
            parsed_job_type = JobType(job_type)
        except ValueError:
            parsed_job_type = None
    jobs = await service.get_jobs(
        skip=skip,
        limit=limit,
        job_type=parsed_job_type,
        is_remote=is_remote,
        company=company,
    )
    total = await service.job_repo.count({"is_active": True})
    return JobListResponse(jobs=jobs, total=total, skip=skip, limit=limit)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific job."""
    service = JobService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new job."""
    service = JobService(db)
    try:
        job_dict = job_data.model_dump()
        job_dict.setdefault("source", "manual")
        return await service.create_job(job_dict)
    except DuplicateJobError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create job") from e


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_data: JobUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a job."""
    service = JobService(db)
    updates = {k: v for k, v in job_data.model_dump().items() if v is not None}
    job = await service.job_repo.update(job_id, updates)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a job."""
    service = JobService(db)
    deleted = await service.job_repo.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/search", response_model=JobListResponse)
async def search_jobs(
    search: JobSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search jobs."""
    service = JobService(db)
    jobs = await service.search_jobs(search.query, search.limit)
    return JobListResponse(jobs=jobs, total=len(jobs), skip=0, limit=search.limit)


@router.get("/stats/overview", response_model=JobStatistics)
async def get_job_statistics(
    db: AsyncSession = Depends(get_db),
):
    """Get job statistics."""
    service = JobService(db)
    return await service.get_job_statistics()


@router.get("/closing/soon", response_model=list[JobResponse])
async def get_closing_soon(
    days: int = Query(2, ge=1, le=7),
    db: AsyncSession = Depends(get_db),
):
    """Get jobs closing soon."""
    service = JobService(db)
    return await service.get_closing_soon(days)


@router.post("/discovery/run")
async def run_discovery(
    source: str | None = None,
    query: str = "python developer",
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Run job discovery from sources.

    Accepts the query either as a query parameter (?query=...) for
    backward compatibility or in the JSON body ({"query": ...}) which
    is what the Streamlit dashboard sends. The body value wins so the
    dashboard's "Run Discovery" button searches what the user typed
    instead of silently falling back to the default.
    """
    if body and body.get("query"):
        query = body["query"]
    from interntrack.scrapers.registry import get_default_registry

    registry = get_default_registry()
    jobs = await registry.fetch_all(query=query, sources=[source] if source else None)
    service = JobService(db)
    saved = await service.save_jobs(jobs)

    # Notify configured channels when new jobs were saved (no-op otherwise).
    if saved:
        from interntrack.services.notification_service import NotificationManager

        with contextlib.suppress(Exception):
            message = (
                f"🚀 Job Discovery\n\n"
                f"Query: {query}\n"
                f"Found: {len(jobs)} · Newly saved: {len(saved)}\n\n"
                f"Check the dashboard or the Jobs page to review them."
            )
            await NotificationManager(db).notify_all(
                message,
                subject="New Jobs Found",
            )

    return {"discovered": len(jobs), "saved": len(saved)}
