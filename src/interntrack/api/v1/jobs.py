"""
Jobs API endpoints.
"""

from typing import List, Optional

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
from interntrack.services.job_service import JobService
from interntrack.domain.exceptions import DuplicateJobError

router = APIRouter()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    job_type: Optional[str] = None,
    is_remote: Optional[bool] = None,
    company: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List jobs with filters."""
    service = JobService(db)
    jobs = await service.get_jobs(
        skip=skip,
        limit=limit,
        job_type=job_type,
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
        job = await service.create_job(job_dict)
        return job
    except DuplicateJobError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create job")


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


@router.get("/closing/soon", response_model=List[JobResponse])
async def get_closing_soon(
    days: int = Query(2, ge=1, le=7),
    db: AsyncSession = Depends(get_db),
):
    """Get jobs closing soon."""
    service = JobService(db)
    return await service.get_closing_soon(days)


@router.post("/discovery/run")
async def run_discovery(
    source: Optional[str] = None,
    query: str = "python developer",
    db: AsyncSession = Depends(get_db),
):
    """Run job discovery from sources."""
    from interntrack.scrapers.registry import get_default_registry

    registry = get_default_registry()
    jobs = await registry.fetch_all(query=query, sources=[source] if source else None)
    service = JobService(db)
    saved = await service.save_jobs(jobs)
    return {"discovered": len(jobs), "saved": len(saved)}
