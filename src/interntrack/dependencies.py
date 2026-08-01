"""
Dependency injection module.
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.config import Settings, get_settings
from interntrack.database.session import get_db_session
from interntrack.services.ai_service import AIService
from interntrack.services.application_service import ApplicationService
from interntrack.services.job_service import JobService
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService


@lru_cache
def get_settings_cached() -> Settings:
    """Get cached settings."""
    return get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async with get_db_session() as session:
        yield session


async def get_job_service(db: AsyncSession | None = None) -> JobService:
    """Get job service."""
    if db is None:
        async with get_db_session() as session:
            return JobService(session)
    return JobService(db)


async def get_application_service(db: AsyncSession | None = None) -> ApplicationService:
    """Get application service."""
    if db is None:
        async with get_db_session() as session:
            return ApplicationService(session)
    return ApplicationService(db)


async def get_notification_manager(
    db: AsyncSession | None = None,
) -> NotificationManager:
    """Get notification manager."""
    if db is None:
        async with get_db_session() as session:
            return NotificationManager(session)
    return NotificationManager(db)


async def get_report_service(db: AsyncSession | None = None) -> ReportService:
    """Get report service."""
    if db is None:
        async with get_db_session() as session:
            return ReportService(session)
    return ReportService(db)


async def get_ai_service(
    db: AsyncSession | None = None,
) -> AIService:
    """Get AI service."""
    if db is None:
        async with get_db_session() as session:
            return AIService(session)
    return AIService(db)
