"""
Jobs API Router

Endpoints for job operations: search, list, get, create, update, delete.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from cybershield.dependencies import get_job_repository
from cybershield.repositories.job_repository import JobRepository
from cybershield.schemas.job import JobCreate, JobListResponse, JobResponse, JobUpdate

router = APIRouter()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    country: Optional[str] = None,
    job_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    repo: JobRepository = Depends(get_job_repository),
):
    """List jobs with filtering and pagination."""
    filters = {}
    if country:
        filters["country"] = country
    if job_type:
        filters["job_type"] = job_type
    if experience_level:
        filters["experience_level"] = experience_level

    jobs = await repo.get_all(skip=skip, limit=limit, filters=filters)
    total = await repo.count(filters=filters)

    return {
        "items": jobs,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/search", response_model=JobListResponse)
async def search_jobs(
    q: str = Query(..., min_length=1),
    country: Optional[str] = None,
    job_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    repo: JobRepository = Depends(get_job_repository),
):
    """Search jobs with text query and filters."""
    jobs = await repo.search_jobs(
        query_text=q,
        country=country,
        job_type=job_type,
        experience_level=experience_level,
        skip=skip,
        limit=limit,
    )
    return {
        "items": jobs,
        "total": len(jobs),
        "skip": skip,
        "limit": limit,
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    repo: JobRepository = Depends(get_job_repository),
):
    """Get job by ID with full details."""
    job = await repo.get_full(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    job_data: JobCreate,
    repo: JobRepository = Depends(get_job_repository),
):
    """Create a new job listing."""
    job = await repo.create(job_data.model_dump())
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_data: JobUpdate,
    repo: JobRepository = Depends(get_job_repository),
):
    """Update an existing job listing."""
    job = await repo.update(job_id, job_data.model_dump(exclude_unset=True))
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    repo: JobRepository = Depends(get_job_repository),
):
    """Delete a job listing."""
    deleted = await repo.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/expiring-soon", response_model=List[JobResponse])
async def get_expiring_jobs(
    days: int = Query(7, ge=1, le=30),
    repo: JobRepository = Depends(get_job_repository),
):
    """Get jobs expiring within specified days."""
    jobs = await repo.get_expiring_soon(days=days)
    return jobs
