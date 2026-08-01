"""
Dependency Injection

Provides database sessions and repository instances.
"""

import logging
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.config import get_settings
from cybershield.database.session import get_db_session
from cybershield.notifications.orchestrator import (
    NotificationOrchestrator,
    create_default_orchestrator,
)
from cybershield.repositories.application_repository import ApplicationRepository
from cybershield.repositories.company_repository import CompanyRepository
from cybershield.repositories.job_repository import JobRepository
from cybershield.repositories.skill_repository import SkillRepository
from cybershield.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# Global notification orchestrator instance
_notification_orchestrator: NotificationOrchestrator | None = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with get_db_session() as session:
        yield session


def get_job_repository(session: AsyncSession = Depends(get_session)) -> JobRepository:
    """Get job repository instance."""
    return JobRepository(session)


def get_application_repository(session: AsyncSession = Depends(get_session)) -> ApplicationRepository:
    """Get application repository instance."""
    return ApplicationRepository(session)


def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    """Get user repository instance."""
    return UserRepository(session)


def get_company_repository(session: AsyncSession = Depends(get_session)) -> CompanyRepository:
    """Get company repository instance."""
    return CompanyRepository(session)


def get_skill_repository(session: AsyncSession = Depends(get_session)) -> SkillRepository:
    """Get skill repository instance."""
    return SkillRepository(session)


def get_notification_orchestrator() -> NotificationOrchestrator:
    """Get or create the global notification orchestrator with configured channels."""
    global _notification_orchestrator
    if _notification_orchestrator is None:
        try:
            settings = get_settings()
            config: dict = {}
            if settings.telegram_bot_token:
                config["telegram"] = {
                    "bot_token": settings.telegram_bot_token,
                    "chat_id": settings.telegram_chat_id,
                }
            if settings.smtp_user:
                config["email"] = {
                    "host": settings.smtp_host,
                    "port": settings.smtp_port,
                    "user": settings.smtp_user,
                    "password": settings.smtp_password,
                    "from_address": settings.email_from,
                }
            if settings.discord_webhook_url:
                config["discord"] = {"webhook_url": settings.discord_webhook_url}
            if settings.slack_webhook_url:
                config["slack"] = {"webhook_url": settings.slack_webhook_url}
            _notification_orchestrator = create_default_orchestrator(config)
        except (FileNotFoundError, ValueError, AttributeError, Exception) as e:
            # Catch-all for settings initialization failures
            logger.warning(f"Failed to initialize notification orchestrator from settings: {e}")
            _notification_orchestrator = NotificationOrchestrator()
    return _notification_orchestrator
