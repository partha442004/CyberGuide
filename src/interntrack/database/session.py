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
    """Initialize database tables and reconcile schema drift."""
    from interntrack.domain.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all never alters existing tables; sync drifted columns so a
        # pre-existing database (e.g. the Railway Postgres created before a
        # column was added to a model) is brought up to date on startup.
        await conn.run_sync(_sync_missing_columns)


def _sync_missing_columns(sync_conn) -> None:
    """Idempotently add model columns missing from existing tables.

    ``create_all`` only creates tables that don't exist yet — it never adds
    new columns to an existing table. A database initialized from an older
    model (e.g. the Railway Postgres ``jobs`` table created before the
    ``tags`` column existed) would otherwise fail at runtime with
    ``UndefinedColumnError`` on every ``SELECT *`` of that table.

    For every model table that already exists, this compares the model's
    columns against the live table and issues ``ALTER TABLE ... ADD COLUMN``
    for the missing ones. Only nullable/defaulted columns are added, so an
    existing row can never violate a NOT NULL constraint (a hard-failing
    column would surface at startup, inside the surrounding ``begin()``
    transaction, and be rolled back atomically).
    """
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    from interntrack.domain.models import Base

    inspector = sa_inspect(sync_conn)
    table_names = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in table_names:
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            if not column.nullable and column.default is None:
                continue
            col_type = column.type.compile(dialect=sync_conn.dialect)
            stmt = text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}")
            sync_conn.execute(stmt)


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
