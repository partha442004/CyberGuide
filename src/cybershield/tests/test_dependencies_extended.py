"""
Unit Tests for Dependency Injection (extended)

Covers the remaining lines of ``cybershield/dependencies.py``:
- ``get_session`` generator
- All five repository factory getters
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.dependencies import (
    get_application_repository,
    get_company_repository,
    get_job_repository,
    get_session,
    get_skill_repository,
    get_user_repository,
)
from cybershield.repositories.application_repository import ApplicationRepository
from cybershield.repositories.company_repository import CompanyRepository
from cybershield.repositories.job_repository import JobRepository
from cybershield.repositories.skill_repository import SkillRepository
from cybershield.repositories.user_repository import UserRepository


class TestGetSession:
    """Tests for the async session generator."""

    @pytest.mark.asyncio
    async def test_yields_session_from_db_session(self):
        """get_session should delegate to get_db_session and yield its session."""
        session = AsyncMock()

        # get_db_session is an @asynccontextmanager, so its return value must
        # support the async context manager protocol.
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock(return_value=False)

        with patch("cybershield.dependencies.get_db_session") as mock_db:
            mock_db.return_value = context_manager
            generator = get_session()
            result = await generator.__anext__()
            assert result is session
            with pytest.raises(StopAsyncIteration):
                await generator.__anext__()


class TestRepositoryGetters:
    """Tests for all repository factory functions."""

    @pytest.mark.asyncio
    async def test_get_job_repository(self):
        """Should return a JobRepository bound to the session."""
        session = AsyncMock()
        repo = get_job_repository(session)
        assert isinstance(repo, JobRepository)
        assert repo.session is session

    @pytest.mark.asyncio
    async def test_get_application_repository(self):
        """Should return an ApplicationRepository bound to the session."""
        session = AsyncMock()
        repo = get_application_repository(session)
        assert isinstance(repo, ApplicationRepository)
        assert repo.session is session

    @pytest.mark.asyncio
    async def test_get_user_repository(self):
        """Should return a UserRepository bound to the session."""
        session = AsyncMock()
        repo = get_user_repository(session)
        assert isinstance(repo, UserRepository)
        assert repo.session is session

    @pytest.mark.asyncio
    async def test_get_company_repository(self):
        """Should return a CompanyRepository bound to the session."""
        session = AsyncMock()
        repo = get_company_repository(session)
        assert isinstance(repo, CompanyRepository)
        assert repo.session is session

    @pytest.mark.asyncio
    async def test_get_skill_repository(self):
        """Should return a SkillRepository bound to the session."""
        session = AsyncMock()
        repo = get_skill_repository(session)
        assert isinstance(repo, SkillRepository)
        assert repo.session is session
