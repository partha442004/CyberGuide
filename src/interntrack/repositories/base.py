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

    async def get_by_id(self, obj_id: str) -> ModelType | None:
        """Get a record by ID."""
        id_col = self.model.id  # type: ignore[attr-defined]
        result = await self.session.execute(
            select(self.model).where(id_col == obj_id),
        )
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
        return result.scalar() or 0

    async def create(self, obj: ModelType) -> ModelType:
        """Create a new record."""
        obj_id = getattr(obj, "id", None)
        if not obj_id:
            obj.id = str(uuid4())  # type: ignore[attr-defined]
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def create_many(self, objects: list[ModelType]) -> list[ModelType]:
        """Create multiple records."""
        for obj in objects:
            if not getattr(obj, "id", None):
                obj.id = str(uuid4())  # type: ignore[attr-defined]
            self.session.add(obj)
        await self.session.flush()
        return objects

    async def update(self, obj_id: str, updates: dict) -> ModelType | None:
        """Update a record by ID."""
        obj = await self.get_by_id(obj_id)
        if obj:
            for key, value in updates.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            await self.session.flush()
        return obj

    async def delete(self, obj_id: str) -> bool:
        """Delete a record by ID."""
        obj = await self.get_by_id(obj_id)
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
            return True
        return False

    async def exists(self, obj_id: str) -> bool:
        """Check if a record exists."""
        id_col = self.model.id  # type: ignore[attr-defined]
        result = await self.session.execute(
            select(id_col).where(id_col == obj_id),
        )
        return result.scalar_one_or_none() is not None
