"""
Job repository with job-specific queries.
"""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import JobSource, JobType
from interntrack.domain.models import Job
from interntrack.repositories.base import BaseRepository
from interntrack.utils.helpers import utcnow


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
        cutoff_date = utcnow() - timedelta(days=tolerance_days)
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
        query = select(Job).where(Job.is_active)

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
        """Get active jobs (posted in the last N days).

        Uses ``is_active`` rather than a ``created_at`` cutoff to avoid
        tz-aware / tz-naive comparison failures on Neon + asyncpg.
        Returns empty list for non-positive ``days``.
        """
        if days <= 0:
            return []
        query = (
            select(Job).where(Job.is_active).order_by(Job.created_at.desc()).limit(200)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_closing_soon(self, days: int = 2) -> list[Job]:
        """Get jobs closing within N days."""
        now = utcnow()
        cutoff = now + timedelta(days=days)
        query = (
            select(Job)
            .where(
                and_(
                    Job.expires_at.isnot(None),
                    Job.expires_at <= cutoff,
                    Job.expires_at >= now,
                    Job.is_active,
                ),
            )
            .order_by(Job.expires_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_top_companies(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get top companies by job count."""
        query = (
            select(Job.company, func.count(Job.id).label("count"))
            .where(Job.is_active)
            .group_by(Job.company)
            .order_by(func.count(Job.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [tuple(row) for row in result.all()]

    async def search_jobs(self, query_str: str, limit: int = 50) -> list[Job]:
        """Search jobs by title, company, description, or location."""
        search_term = f"%{query_str}%"
        query = (
            select(Job)
            .where(
                and_(
                    Job.is_active,
                    (
                        Job.title.ilike(search_term)
                        | Job.company.ilike(search_term)
                        | Job.description.ilike(search_term)
                        | Job.location.ilike(search_term)
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

    async def get_job_type_distribution(self) -> list[tuple[JobType, int]]:
        """Get job type distribution."""
        query = (
            select(Job.job_type, func.count(Job.id).label("count"))
            .where(Job.is_active)
            .group_by(Job.job_type)
            .order_by(func.count(Job.id).desc())
        )
        result = await self.session.execute(query)
        return [tuple(row) for row in result.all()]

    async def deactivate_expired(self) -> int:
        """Deactivate expired jobs."""
        now = utcnow()
        expired_ids = (
            (
                await self.session.execute(
                    select(Job.id).where(
                        and_(
                            Job.expires_at.isnot(None),
                            Job.expires_at < now,
                            Job.is_active,
                        ),
                    ),
                )
            )
            .scalars()
            .all()
        )

        if expired_ids:
            await self.session.execute(
                update(Job).where(Job.id.in_(expired_ids)).values(is_active=False),
            )
            await self.session.flush()

        return len(expired_ids)

    async def archive_expired_jobs(self, days: int = 30) -> int:
        """Move jobs older than `days` to the expired_jobs archive table.

        Returns the number of jobs archived.
        """
        from datetime import timedelta

        from interntrack.domain.models import ExpiredJob

        cutoff = utcnow() - timedelta(days=days)

        # Find old jobs
        result = await self.session.execute(
            select(Job).where(
                and_(
                    Job.is_active,
                    Job.first_seen_at.isnot(None),
                    Job.first_seen_at < cutoff,
                )
            )
        )
        old_jobs = result.scalars().all()

        if not old_jobs:
            return 0

        archived = 0
        for job in old_jobs:
            # Create archive record
            expired = ExpiredJob(
                id=str(uuid4()),
                original_id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                url=job.url,
                source=job.source.value if job.source else None,
                job_type=job.job_type.value if job.job_type else None,
                experience_level=job.experience_level.value
                if job.experience_level
                else None,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                is_remote=job.is_remote,
                tags=job.tags,
                expired_at=utcnow(),
                reason="stale",
                original_created_at=job.created_at,
            )
            self.session.add(expired)

            # Mark original as inactive
            job.is_active = False  # type: ignore[assignment]
            archived += 1

        await self.session.commit()
        return archived

    async def get_expired_jobs(self, limit: int = 50) -> list:
        """Get archived expired jobs."""
        from interntrack.domain.models import ExpiredJob

        result = await self.session.execute(
            select(ExpiredJob).order_by(ExpiredJob.expired_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_fresh_jobs(self, limit: int = 100) -> list[Job]:
        """Get only fresh jobs (not expired, not stale)."""
        from datetime import timedelta

        cutoff = utcnow() - timedelta(days=30)
        result = await self.session.execute(
            select(Job)
            .where(
                and_(
                    Job.is_active,
                    or_(
                        Job.first_seen_at.is_(None),
                        Job.first_seen_at >= cutoff,
                    ),
                )
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
