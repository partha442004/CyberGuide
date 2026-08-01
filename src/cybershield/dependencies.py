"""
Dependency Injection

Provides database sessions and repository instances.
"""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.database.session import get_db_session
from cybershield.repositories.application_repository import ApplicationRepository
from cybershield.repositories.company_repository import CompanyRepository
from cybershield.repositories.job_repository import JobRepository
from cybershield.repositories.skill_repository import SkillRepository
from cybershield.repositories.user_repository import UserRepository


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with get_db_session() as session:
        yield session


def get_job_repository(session: AsyncSession = Depends(get_session)) -> JobRepository:
    """Get job repository instance."""
    return JobRepository(session)


def get_application_repository(
    session: AsyncSession = Depends(get_session),
) -> ApplicationRepository:
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
