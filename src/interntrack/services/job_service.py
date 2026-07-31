"""
Job service for job management and discovery orchestration.
"""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import JobSource, JobType
from interntrack.domain.exceptions import DuplicateJobError, ScrapingError
from interntrack.domain.models import Job
from interntrack.repositories.job_repository import JobRepository


class JobService:
    """Job service for job management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)

    async def create_job(self, job_data: dict) -> Job:
        """Create a new job, checking for duplicates."""
        existing = await self.job_repo.get_by_url(job_data.get("url", ""))
        if existing:
            raise DuplicateJobError(
                job_data.get("title", "Unknown"),
                job_data.get("company", "Unknown"),
            )

        job = Job(**job_data)
        return await self.job_repo.create(job)

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return await self.job_repo.get_by_id(job_id)

    async def get_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        job_type: Optional[JobType] = None,
        is_remote: Optional[bool] = None,
        company: Optional[str] = None,
    ) -> List[Job]:
        """Get jobs with filters."""
        return await self.job_repo.get_active_jobs(
            skip=skip,
            limit=limit,
            job_type=job_type,
            is_remote=is_remote,
            company=company,
        )

    async def search_jobs(self, query: str, limit: int = 50) -> List[Job]:
        """Search jobs by query."""
        return await self.job_repo.search_jobs(query, limit)

    async def save_jobs(self, jobs: List[dict]) -> List[Job]:
        """Save multiple jobs, skipping duplicates."""
        saved_jobs = []
        for job_data in jobs:
            try:
                job = await self.create_job(job_data)
                saved_jobs.append(job)
            except DuplicateJobError:
                continue
        return saved_jobs

    async def get_job_statistics(self) -> dict:
        """Get job statistics."""
        top_companies_raw = await self.job_repo.get_top_companies()
        job_types_raw = await self.job_repo.get_job_type_distribution()
        
        return {
            "total_jobs": await self.job_repo.count({"is_active": True}),
            "salary_stats": await self.job_repo.get_salary_statistics(),
            "top_companies": [{"company": c, "jobs": n} for c, n in top_companies_raw],
            "job_types": [{"type": t.value if hasattr(t, 'value') else str(t), "count": n} for t, n in job_types_raw],
        }

    async def get_closing_soon(self, days: int = 2) -> List[Job]:
        """Get jobs closing soon."""
        return await self.job_repo.get_closing_soon(days)

    async def deactivate_expired(self) -> int:
        """Deactivate expired jobs."""
        return await self.job_repo.deactivate_expired()
