"""
Base repository with common CRUD operations.
"""

from typing import Generic, TypeVar
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: str) -> ModelType | None:
        """Get a record by ID."""
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[ModelType]:
        """Get all records with optional filters."""
        query = select(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, filters: dict | None = None) -> int:
        """Count records with optional filters."""
        from sqlalchemy import func

        query = select(func.count()).select_from(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        result = await self.session.execute(query)
        return result.scalar()

    async def create(self, obj: ModelType) -> ModelType:
        """Create a new record."""
        if not obj.id:
            obj.id = str(uuid4())
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def create_many(self, objects: list[ModelType]) -> list[ModelType]:
        """Create multiple records."""
        for obj in objects:
            if not obj.id:
                obj.id = str(uuid4())
            self.session.add(obj)
        await self.session.flush()
        return objects

    async def update(self, id: str, updates: dict) -> ModelType | None:
        """Update a record by ID."""
        obj = await self.get_by_id(id)
        if obj:
            for key, value in updates.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            await self.session.flush()
        return obj

    async def delete(self, id: str) -> bool:
        """Delete a record by ID."""
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
            return True
        return False

    async def exists(self, id: str) -> bool:
        """Check if a record exists."""
        result = await self.session.execute(
            select(self.model.id).where(self.model.id == id),
        )
        return result.scalar_one_or_none() is not None
