"""
Job Repository

Specialized repository for job-related operations.
"""

from datetime import timedelta
from typing import List, Optional, Sequence

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cybershield.domain.models import DuplicateGroup, Job, ScamScore
from cybershield.repositories.base import BaseRepository
from cybershield.utils import utcnow


class JobRepository(BaseRepository[Job]):
    """Repository for Job operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Job, session)

    async def get_with_skills(self, id: str) -> Optional[Job]:
        """Get job with job_skills relationships."""
        result = await self.session.execute(
            select(Job).options(selectinload(Job.skills)).where(Job.id == id)
        )
        return result.scalar_one_or_none()

    async def get_full(self, id: str) -> Optional[Job]:
        """Get job with all relationships."""
        result = await self.session.execute(
            select(Job)
            .options(selectinload(Job.skills))
            .options(selectinload(Job.applications))
            .options(selectinload(Job.scam_score))
            .where(Job.id == id)
        )
        return result.scalar_one_or_none()

    async def search_jobs(
        self,
        query_text: str,
        country: Optional[str] = None,
        job_type: Optional[str] = None,
        experience_level: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[Job]:
        """Search jobs with multiple filters."""
        stmt = select(Job).where(Job.is_active)

        # Text search - search in title, description, and company name
        if query_text:
            search_pattern = f"%{query_text}%"
            stmt = stmt.where(
                or_(
                    Job.title.ilike(search_pattern),
                    Job.description.ilike(search_pattern),
                    Job.company.ilike(search_pattern),
                )
            )

        # Filters
        if country:
            stmt = stmt.where(Job.country == country)
        if job_type:
            stmt = stmt.where(Job.job_type == job_type)
        if experience_level:
            stmt = stmt.where(Job.experience_level == experience_level)

        # Ordering and pagination
        stmt = stmt.order_by(desc(Job.posted_at)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_source(self, source: str, limit: int = 100) -> Sequence[Job]:
        """Get jobs from a specific source."""
        result = await self.session.execute(
            select(Job).where(Job.source == source).order_by(desc(Job.posted_at)).limit(limit)
        )
        return result.scalars().all()

    async def get_expiring_soon(self, days: int = 7) -> Sequence[Job]:
        """Get jobs expiring within specified days."""
        now = utcnow()
        future = now + timedelta(days=days)

        result = await self.session.execute(
            select(Job)
            .where(
                and_(
                    Job.is_active,
                    Job.expires_at <= future,
                    Job.expires_at >= now,
                )
            )
            .order_by(Job.expires_at)
        )
        return result.scalars().all()

    async def get_high_scam_risk(self, threshold: float = 50.0) -> Sequence[Job]:
        """Get jobs with high scam scores using SQL filter."""
        result = await self.session.execute(
            select(Job)
            .join(ScamScore, Job.id == ScamScore.job_id)
            .where(
                and_(
                    Job.is_active,
                    ScamScore.scam_score >= threshold,
                )
            )
            .order_by(desc(ScamScore.scam_score))
        )
        return result.scalars().all()

    async def mark_duplicates(self, job_ids: List[str], canonical_id: str) -> None:
        """Mark jobs as duplicates of a canonical job."""
        for job_id in job_ids:
            if job_id != canonical_id:
                job = await self.get(job_id)
                if job:
                    job.is_active = False  # type: ignore[assignment]
                    dup_group = DuplicateGroup(
                        canonical_job_id=canonical_id,
                        duplicate_job_id=job_id,
                        similarity_score=1.0,
                        match_type="manual",
                    )
                    self.session.add(dup_group)
        await self.session.flush()

    async def update_verification_status(self, job_id: str, is_verified: bool) -> Job:
        """Update job verification status."""
        job = await self.get_or_raise(job_id)
        job.is_verified = is_verified  # type: ignore[assignment]
        job.updated_at = utcnow()  # type: ignore[assignment]
        await self.session.flush()
        return job
