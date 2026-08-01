"""
Job repository with job-specific queries.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import JobSource, JobType
from interntrack.domain.models import Job
from interntrack.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    """Job repository with job-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(Job, session)

    async def get_by_url(self, url: str) -> Job | None:
        """Get a job by URL (for deduplication)."""
        result = await self.session.execute(select(Job).where(Job.url == url))
        return result.scalar_one_or_none()

    async def find_duplicate(
        self,
        title: str,
        company: str,
        source: JobSource,
        tolerance_days: int = 7,
    ) -> Job | None:
        """Find potential duplicate job posting."""
        cutoff_date = datetime.now(UTC) - timedelta(days=tolerance_days)
        query = select(Job).where(
            and_(
                func.lower(Job.title) == title.lower(),
                func.lower(Job.company) == company.lower(),
                Job.source == source,
                Job.created_at >= cutoff_date,
            ),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        job_type: JobType | None = None,
        is_remote: bool | None = None,
        company: str | None = None,
    ) -> list[Job]:
        """Get active jobs with filters."""
        query = select(Job).where(Job.is_active == True)

        if job_type:
            query = query.where(Job.job_type == job_type)
        if is_remote is not None:
            query = query.where(Job.is_remote == is_remote)
        if company:
            query = query.where(func.lower(Job.company) == company.lower())

        query = query.order_by(Job.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_jobs_by_source(self, source: JobSource) -> list[Job]:
        """Get all jobs from a specific source."""
        query = select(Job).where(Job.source == source)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_jobs(self, days: int = 7) -> list[Job]:
        """Get jobs posted in the last N days."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        query = (
            select(Job)
            .where(Job.created_at >= cutoff_date)
            .order_by(Job.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_closing_soon(self, days: int = 2) -> list[Job]:
        """Get jobs closing within N days."""
        now = datetime.now(UTC)
        cutoff = now + timedelta(days=days)
        query = (
            select(Job)
            .where(
                and_(
                    Job.expires_at.isnot(None),
                    Job.expires_at <= cutoff,
                    Job.expires_at >= now,
                    Job.is_active == True,
                ),
            )
            .order_by(Job.expires_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_top_companies(self, limit: int = 10) -> list[tuple]:
        """Get top companies by job count."""
        query = (
            select(Job.company, func.count(Job.id).label("count"))
            .where(Job.is_active == True)
            .group_by(Job.company)
            .order_by(func.count(Job.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.all())

    async def search_jobs(self, query_str: str, limit: int = 50) -> list[Job]:
        """Search jobs by title, company, or description."""
        search_term = f"%{query_str}%"
        query = (
            select(Job)
            .where(
                and_(
                    Job.is_active == True,
                    (
                        Job.title.ilike(search_term)
                        | Job.company.ilike(search_term)
                        | Job.description.ilike(search_term)
                    ),
                ),
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_salary_statistics(self) -> dict:
        """Get salary statistics across all jobs."""
        query = select(
            func.min(Job.salary_min).label("min_salary"),
            func.max(Job.salary_max).label("max_salary"),
            func.avg(Job.salary_min).label("avg_min"),
            func.avg(Job.salary_max).label("avg_max"),
        ).where(
            and_(Job.salary_min.isnot(None), Job.salary_max.isnot(None)),
        )
        result = await self.session.execute(query)
        row = result.one()
        return {
            "min_salary": row.min_salary,
            "max_salary": row.max_salary,
            "avg_min": round(row.avg_min, 2) if row.avg_min else None,
            "avg_max": round(row.avg_max, 2) if row.avg_max else None,
        }

    async def get_job_type_distribution(self) -> list[tuple]:
        """Get job type distribution."""
        query = (
            select(Job.job_type, func.count(Job.id).label("count"))
            .where(Job.is_active == True)
            .group_by(Job.job_type)
            .order_by(func.count(Job.id).desc())
        )
        result = await self.session.execute(query)
        return list(result.all())

    async def deactivate_expired(self) -> int:
        """Deactivate expired jobs."""
        from sqlalchemy import update

        result = await self.session.execute(
            update(Job)
            .where(
                and_(
                    Job.expires_at.isnot(None),
                    Job.expires_at < datetime.now(UTC),
                    Job.is_active == True,
                ),
            )
            .values(is_active=False),
        )
        await self.session.flush()
        return result.rowcount
