"""
Company Repository

Specialized repository for company operations.
"""

from typing import Optional, Sequence

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cybershield.domain.models import Company, Job
from cybershield.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    """Repository for Company operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Company, session)

    async def get_by_name(self, name: str) -> Optional[Company]:
        """Get company by name (case-insensitive)."""
        result = await self.session.execute(
            select(Company).where(Company.name.ilike(name))
        )
        return result.scalar_one_or_none()

    async def get_or_create_by_name(self, name: str) -> Company:
        """Get existing company or create new one."""
        company = await self.get_by_name(name)
        if not company:
            company = await self.create({"name": name})
        return company

    async def get_with_jobs(self, id: str) -> Optional[Company]:
        """Get company with its job listings."""
        result = await self.session.execute(
            select(Company)
            .options(selectinload(Company.jobs))
            .where(Company.id == id)
        )
        return result.scalar_one_or_none()

    async def search_companies(
        self, query_text: str, limit: int = 20
    ) -> Sequence[Company]:
        """Search companies by name."""
        search_pattern = f"%{query_text}%"
        result = await self.session.execute(
            select(Company)
            .where(Company.name.ilike(search_pattern))
            .order_by(Company.name)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_top_hiring_companies(
        self, limit: int = 10, country: Optional[str] = None
    ) -> Sequence[dict]:
        """Get top companies by job count."""
        query = (
            select(
                Company,
                func.count(Job.id).label("job_count"),
            )
            .join(Job, Company.id == Job.company_id)
            .where(Job.is_active == True)
            .group_by(Company.id)
            .order_by(desc("job_count"))
            .limit(limit)
        )

        if country:
            query = query.where(Job.country == country)

        result = await self.session.execute(query)
        return [
            {"company": row[0], "job_count": row[1]}
            for row in result.all()
        ]

    async def get_trusted_companies(self) -> Sequence[Company]:
        """Get list of known trusted companies."""
        result = await self.session.execute(
            select(Company)
            .where(Company.is_trusted == True)
            .order_by(Company.name)
        )
        return result.scalars().all()

    async def update_trust_status(self, company_id: str, is_trusted: bool) -> Company:
        """Update company trust status."""
        company = await self.get_or_raise(company_id)
        company.is_trusted = is_trusted
        await self.session.flush()
        return company
