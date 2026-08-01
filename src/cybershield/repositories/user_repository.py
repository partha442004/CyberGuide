"""
User Repository

Specialized repository for user management operations.
"""

from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.domain.models import User, Watchlist
from cybershield.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_with_preferences(self, id: str) -> Optional[User]:
        """Get user with preferences (watchlists)."""
        result = await self.session.execute(
            select(User)
            .where(User.id == id)
        )
        return result.scalar_one_or_none()

    async def add_watchlist(self, user_id: str, watch_type: str, value: str) -> Watchlist:
        """Add a watchlist item (company or keyword)."""
        existing = await self.session.execute(
            select(Watchlist).where(
                and_(
                    Watchlist.user_id == user_id,
                    Watchlist.watch_type == watch_type,
                    Watchlist.value == value,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"{watch_type} '{value}' already in watchlist")

        watchlist = Watchlist(
            user_id=user_id,
            watch_type=watch_type,
            value=value,
            is_active=True,
        )
        self.session.add(watchlist)
        await self.session.flush()
        return watchlist

    async def remove_watchlist(self, user_id: str, watch_type: str, value: str) -> bool:
        """Remove a watchlist item."""
        result = await self.session.execute(
            select(Watchlist).where(
                and_(
                    Watchlist.user_id == user_id,
                    Watchlist.watch_type == watch_type,
                    Watchlist.value == value,
                )
            )
        )
        watchlist = result.scalar_one_or_none()
        if watchlist:
            await self.session.delete(watchlist)
            await self.session.flush()
            return True
        return False

    async def get_watchlist(self, user_id: str, watch_type: Optional[str] = None) -> Sequence[Watchlist]:
        """Get user's watchlist items."""
        query = select(Watchlist).where(Watchlist.user_id == user_id)
        if watch_type:
            query = query.where(Watchlist.watch_type == watch_type)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_company_watchlist(self, user_id: str) -> Sequence[Watchlist]:
        """Get user's company watchlist."""
        return await self.get_watchlist(user_id, watch_type="company")

    async def get_keyword_watchlist(self, user_id: str) -> Sequence[Watchlist]:
        """Get user's keyword watchlist."""
        return await self.get_watchlist(user_id, watch_type="keyword")

    async def add_company_watchlist(self, user_id: str, company_id: str) -> Watchlist:
        """Add a company to user's watchlist."""
        return await self.add_watchlist(user_id, watch_type="company", value=company_id)

    async def add_keyword_watchlist(self, user_id: str, keyword: str, category: Optional[str] = None) -> Watchlist:
        """Add a keyword to user's watchlist."""
        watchlist = await self.add_watchlist(user_id, watch_type="keyword", value=keyword)
        # Note: category could be stored if Watchlist model adds a tags column
        return watchlist

    async def remove_company_watchlist(self, user_id: str, company_id: str) -> bool:
        """Remove a company from user's watchlist."""
        return await self.remove_watchlist(user_id, watch_type="company", value=company_id)

    async def remove_keyword_watchlist(self, user_id: str, keyword: str) -> bool:
        """Remove a keyword from user's watchlist."""
        return await self.remove_watchlist(user_id, watch_type="keyword", value=keyword)
