"""
Base Repository

Provides generic CRUD operations for all repositories.
"""

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar
from uuid import uuid4

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from cybershield.domain.exceptions import NotFoundError

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with generic CRUD operations.

    Provides:
    - Create, Read, Update, Delete operations
    - Pagination support
    - Filtering and sorting
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: str) -> Optional[ModelType]:
        """Get a record by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, id: str) -> ModelType:
        """Get a record by ID or raise NotFoundError."""
        record = await self.get(id)
        if not record:
            raise NotFoundError(f"{self.model.__name__} with id {id} not found")
        return record

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = True,
    ) -> Sequence[ModelType]:
        """Get all records with pagination and filtering."""
        query = select(self.model)

        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    column = getattr(self.model, field)
                    if isinstance(value, list):
                        query = query.where(column.in_(value))
                    else:
                        query = query.where(column == value)

        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            column = getattr(self.model, order_by)
            query = query.order_by(desc(column) if order_desc else asc(column))
        else:
            # Default ordering by created_at descending
            if hasattr(self.model, "created_at"):
                query = query.order_by(desc(self.model.created_at))

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        query = select(func.count()).select_from(self.model)

        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    column = getattr(self.model, field)
                    if isinstance(value, list):
                        query = query.where(column.in_(value))
                    else:
                        query = query.where(column == value)

        result = await self.session.execute(query)
        return result.scalar()

    async def create(self, data: Dict[str, Any]) -> ModelType:
        """Create a new record."""
        # Generate ID if not provided
        if "id" not in data:
            data["id"] = str(uuid4())

        record = self.model(**data)
        self.session.add(record)
        await self.session.flush()
        return record

    async def create_many(self, items: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records."""
        records = []
        for data in items:
            if "id" not in data:
                data["id"] = str(uuid4())
            record = self.model(**data)
            self.session.add(record)
            records.append(record)
        await self.session.flush()
        return records

    async def update(self, id: str, data: Dict[str, Any]) -> ModelType:
        """Update a record."""
        record = await self.get_or_raise(id)

        for field, value in data.items():
            if hasattr(record, field):
                setattr(record, field, value)

        await self.session.flush()
        return record

    async def delete(self, id: str) -> bool:
        """Delete a record."""
        record = await self.get(id)
        if not record:
            return False

        await self.session.delete(record)
        await self.session.flush()
        return True

    async def exists(self, id: str) -> bool:
        """Check if a record exists."""
        result = await self.session.execute(
            select(func.count()).where(self.model.id == id)
        )
        return result.scalar() > 0

    async def search(
        self, query_text: str, fields: List[str], limit: int = 10
    ) -> Sequence[ModelType]:
        """Search across multiple fields."""
        query = select(self.model)

        search_conditions = []
        for field in fields:
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                search_conditions.append(column.ilike(f"%{query_text}%"))

        if search_conditions:
            from sqlalchemy import or_
            query = query.where(or_(*search_conditions))

        query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
