"""
Async database session management.
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from interntrack.config import get_settings
from interntrack.metrics import business_metrics_store

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)


def install_db_query_metrics(sync_engine) -> None:
    """Record DB query durations into the business metrics store.

    SQLAlchemy events fire on the sync engine that the async engine wraps;
    the timings are surfaced as ``interntrack_db_queries_total`` and
    ``interntrack_db_query_duration_ms`` on ``/metrics/prometheus``.
    """

    def _before_cursor_execute(
        conn,
        _cursor,
        _statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        # The timestamp rides on ``conn.info`` (public per-connection storage).
        # Unused args are underscore-prefixed so ARG001 is satisfied while
        # keeping SQLAlchemy's positional event signature intact.
        conn.info["_interntrack_query_start"] = time.perf_counter()

    def _after_cursor_execute(
        conn,
        _cursor,
        _statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        start = conn.info.pop("_interntrack_query_start", None)
        if start is not None:
            business_metrics_store.record_db_query(
                (time.perf_counter() - start) * 1000,
            )

    event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(sync_engine, "after_cursor_execute", _after_cursor_execute)


install_db_query_metrics(engine.sync_engine)

# Create session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables."""
    from interntrack.domain.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session as context manager."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI endpoints."""
    async with get_db_session() as session:
        yield session
