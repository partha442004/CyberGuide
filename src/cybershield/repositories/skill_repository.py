"""
Skill Repository

Specialized repository for skill operations and market analysis.
"""

from datetime import timedelta
from typing import Optional, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cybershield.domain.models import JobSkill, Skill, SkillTrend, UserSkill
from cybershield.repositories.base import BaseRepository
from cybershield.utils import utcnow


class SkillRepository(BaseRepository[Skill]):
    """Repository for Skill operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Skill, session)

    async def get_by_name(self, name: str) -> Optional[Skill]:
        """Get skill by name (case-insensitive)."""
        result = await self.session.execute(select(Skill).where(Skill.name.ilike(name)))
        return result.scalar_one_or_none()

    async def get_or_create_by_name(self, name: str, category: Optional[str] = None) -> Skill:
        """Get existing skill or create new one."""
        skill = await self.get_by_name(name)
        if not skill:
            skill = await self.create({"name": name, "category": category})
        return skill

    async def search_skills(self, query_text: str, limit: int = 20) -> Sequence[Skill]:
        """Search skills by name."""
        search_pattern = f"%{query_text}%"
        result = await self.session.execute(
            select(Skill).where(Skill.name.ilike(search_pattern)).order_by(Skill.name).limit(limit)
        )
        return result.scalars().all()

    async def get_trending_skills(self, days: int = 30, limit: int = 10) -> Sequence[dict]:
        """Get trending skills based on recent job postings."""
        from cybershield.domain.models import Job

        query = (
            select(
                Skill,
                func.count(JobSkill.job_id).label("job_count"),
            )
            .join(JobSkill, Skill.id == JobSkill.skill_id)
            .join(Job, JobSkill.job_id == Job.id)
            .where(Job.is_active)
            .group_by(Skill.id)
            .order_by(desc("job_count"))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return [{"skill": row[0], "job_count": row[1]} for row in result.all()]

    async def get_user_skills(self, user_id: str) -> Sequence[UserSkill]:
        """Get all skills for a user."""
        result = await self.session.execute(
            select(UserSkill)
            .options(selectinload(UserSkill.skill))
            .where(UserSkill.user_id == user_id)
        )
        return result.scalars().all()

    async def add_user_skill(
        self, user_id: str, skill_name: str, proficiency: str = "intermediate"
    ) -> UserSkill:
        """Add a skill to user's profile."""
        # Skill.category is NOT NULL, so a newly-created skill needs a fallback.
        skill = await self.get_or_create_by_name(skill_name, category="general")

        user_skill = UserSkill(
            user_id=user_id,
            skill_id=skill.id,
            proficiency_level=proficiency,
        )
        self.session.add(user_skill)
        await self.session.flush()
        return user_skill

    async def get_skill_market_data(self) -> Sequence[dict]:
        """Get market data for all skills."""
        query = (
            select(
                Skill,
                func.count(JobSkill.job_id).label("demand_count"),
            )
            .outerjoin(JobSkill, Skill.id == JobSkill.skill_id)
            .group_by(Skill.id)
            .order_by(desc("demand_count"))
        )

        result = await self.session.execute(query)
        return [
            {
                "skill": row[0],
                "demand_count": row[1],
            }
            for row in result.all()
        ]

    async def get_skill_trends(self, skill_id: str, months: int = 12) -> Sequence[SkillTrend]:
        """Get historical trend data for a skill."""
        cutoff_date = utcnow() - timedelta(days=months * 30)

        result = await self.session.execute(
            select(SkillTrend)
            .where(
                SkillTrend.skill_id == skill_id,
                SkillTrend.period_start >= cutoff_date,
            )
            .order_by(SkillTrend.period_start)
        )
        return result.scalars().all()
