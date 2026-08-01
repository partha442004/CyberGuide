"""
Skill repository for skill management.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import SkillCategory
from interntrack.domain.models import Skill
from interntrack.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    """Skill repository with skill-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(Skill, session)

    async def get_by_name(self, name: str) -> Skill | None:
        """Get skill by name."""
        result = await self.session.execute(
            select(Skill).where(Skill.name == name.lower()),
        )
        return result.scalar_one_or_none()

    async def get_by_category(self, category: SkillCategory) -> list[Skill]:
        """Get all skills in a category."""
        result = await self.session.execute(
            select(Skill).where(Skill.category == category),
        )
        return list(result.scalars().all())

    async def search_skills(self, query_str: str) -> list[Skill]:
        """Search skills by name."""
        search_term = f"%{query_str}%"
        result = await self.session.execute(
            select(Skill).where(Skill.name.ilike(search_term)),
        )
        return list(result.scalars().all())

    async def get_active_skills(self) -> list[Skill]:
        """Get all active skills."""
        result = await self.session.execute(
            select(Skill).where(Skill.is_active),
        )
        return list(result.scalars().all())

    async def create_or_get(self, name: str, category: SkillCategory) -> Skill:
        """Create a skill if it doesn't exist, or return existing."""
        existing = await self.get_by_name(name)
        if existing:
            return existing

        skill = Skill(name=name.lower(), category=category)
        return await self.create(skill)
