"""
Async database session management for CyberShield.

Supports both SQLite (development) and PostgreSQL (production).
Uses lazy initialization to avoid import-time errors when env vars aren't set.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Lazy-initialized globals
_engine = None
_async_session_factory = None


def _get_engine_kwargs() -> dict:
    """Get engine configuration based on database URL."""
    from cybershield.config import get_settings

    settings = get_settings()
    kwargs: dict[str, Any] = {
        "echo": settings.debug,
        "pool_pre_ping": True,
    }

    if "postgresql" in settings.database_url:
        # PostgreSQL connection pooling for production
        kwargs.update({
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 1800,
        })
        logger.info("Using PostgreSQL connection pool")
    else:
        # SQLite specific settings
        kwargs["connect_args"] = {"check_same_thread": False}
        logger.info("Using SQLite database")

    return kwargs


def get_engine():
    """Get or create the async engine (lazy initialization)."""
    global _engine
    if _engine is None:
        from cybershield.config import get_settings

        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            **_get_engine_kwargs(),
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory (lazy initialization)."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory



async def init_db() -> None:
    """Initialize database tables."""
    from cybershield.domain.models import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections."""
    await get_engine().dispose()
    logger.info("Database connections closed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session as context manager."""
    async with get_session_factory()() as session:
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
