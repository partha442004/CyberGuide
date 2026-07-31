"""
User repository for user profile and preferences.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.models import UserSkill, Bookmark, Watchlist
from interntrack.repositories.base import BaseRepository


class UserRepository:
    """User repository for managing user data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_skills(self, user_id: str) -> List[UserSkill]:
        """Get all skills for a user."""
        result = await self.session.execute(
            select(UserSkill).where(UserSkill.user_id == user_id)
        )
        return list(result.scalars().all())

    async def add_user_skill(
        self, user_id: str, skill_id: str, proficiency: int = 1
    ) -> UserSkill:
        """Add a skill to user profile."""
        user_skill = UserSkill(
            user_id=user_id,
            skill_id=skill_id,
            proficiency_level=proficiency,
        )
        self.session.add(user_skill)
        await self.session.flush()
        return user_skill

    async def update_skill_proficiency(
        self, user_id: str, skill_id: str, proficiency: int
    ) -> Optional[UserSkill]:
        """Update skill proficiency."""
        result = await self.session.execute(
            select(UserSkill).where(
                UserSkill.user_id == user_id,
                UserSkill.skill_id == skill_id,
            )
        )
        user_skill = result.scalar_one_or_none()
        if user_skill:
            user_skill.proficiency_level = proficiency
            await self.session.flush()
        return user_skill

    async def get_bookmarks(
        self, user_id: str, item_type: Optional[str] = None
    ) -> List[Bookmark]:
        """Get user bookmarks."""
        query = select(Bookmark)
        if item_type:
            query = query.where(Bookmark.item_type == item_type)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add_bookmark(
        self, item_type: str, item_id: str, notes: Optional[str] = None
    ) -> Bookmark:
        """Add a bookmark."""
        bookmark = Bookmark(
            item_type=item_type,
            item_id=item_id,
            notes=notes,
        )
        self.session.add(bookmark)
        await self.session.flush()
        return bookmark

    async def remove_bookmark(self, bookmark_id: str) -> bool:
        """Remove a bookmark."""
        result = await self.session.execute(
            select(Bookmark).where(Bookmark.id == bookmark_id)
        )
        bookmark = result.scalar_one_or_none()
        if bookmark:
            await self.session.delete(bookmark)
            await self.session.flush()
            return True
        return False

    async def get_watchlists(self, watch_type: Optional[str] = None) -> List[Watchlist]:
        """Get watchlists."""
        query = select(Watchlist).where(Watchlist.is_active == True)
        if watch_type:
            query = query.where(Watchlist.watch_type == watch_type)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def add_watchlist(
        self, watch_type: str, value: str, notification_channels: Optional[list] = None
    ) -> Watchlist:
        """Add a watchlist entry."""
        watchlist = Watchlist(
            watch_type=watch_type,
            value=value,
            notification_channels=notification_channels or ["email"],
        )
        self.session.add(watchlist)
        await self.session.flush()
        return watchlist
