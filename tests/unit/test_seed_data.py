"""Unit tests for scripts/seed_data.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.domain.enums import (
    ApplicationStatus,
    ExperienceLevel,
    JobSource,
    JobType,
    SkillCategory,
)


class TestSeedDatabase:
    """Tests for the async seed_database function."""

    @pytest.mark.asyncio
    async def test_seed_database_creates_skills(self):
        """Test seed_database creates all sample skills."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.seed_data.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import SAMPLE_SKILLS, seed_database

            await seed_database()

        # Verify skills were added
        assert mock_session.add.call_count >= len(SAMPLE_SKILLS)

    @pytest.mark.asyncio
    async def test_seed_database_creates_jobs(self):
        """Test seed_database creates all sample jobs."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.seed_data.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import SAMPLE_JOBS, SAMPLE_SKILLS, seed_database

            await seed_database()

        # Skills + Jobs + JobSkills + UserSkills + Applications
        total_adds = len(SAMPLE_SKILLS) + len(SAMPLE_JOBS)
        assert mock_session.add.call_count >= total_adds

    @pytest.mark.asyncio
    async def test_seed_database_calls_init_db(self):
        """Test seed_database calls init_db."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_init_db = AsyncMock()

        with (
            patch("interntrack.scripts.seed_data.init_db", mock_init_db),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import seed_database

            await seed_database()

        mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_database_commits(self):
        """Test seed_database commits the session."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.seed_data.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import seed_database

            await seed_database()

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_database_creates_user_skills(self):
        """Test seed_database creates user skills for demo user."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.seed_data.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import SAMPLE_SKILLS, seed_database

            await seed_database()

        # UserSkills are added for: python, javascript, react, git, sql
        # That's 5 user skills
        user_skill_calls = [
            c
            for c in mock_session.add.call_args_list
            if c[0][0].__class__.__name__ == "UserSkill"
        ]
        assert len(user_skill_calls) == 5

    @pytest.mark.asyncio
    async def test_seed_database_creates_applications(self):
        """Test seed_database creates sample applications."""
        mock_session = AsyncMock()

        # Create mock jobs to return from the query
        mock_jobs = [
            MagicMock(id="job-1", title="Job 1"),
            MagicMock(id="job-2", title="Job 2"),
            MagicMock(id="job-3", title="Job 3"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_jobs
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.seed_data.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import seed_database

            await seed_database()

        # 3 applications for 3 jobs
        app_calls = [
            c
            for c in mock_session.add.call_args_list
            if c[0][0].__class__.__name__ == "Application"
        ]
        assert len(app_calls) == 3

    @pytest.mark.asyncio
    async def test_seed_database_application_statuses(self):
        """Test seed_database creates applications with correct statuses."""
        mock_session = AsyncMock()

        mock_jobs = [
            MagicMock(id="job-1", title="Job 1"),
            MagicMock(id="job-2", title="Job 2"),
            MagicMock(id="job-3", title="Job 3"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_jobs
        mock_session.execute.return_value = mock_result

        mock_get_db = MagicMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        with (
            patch("interntrack.scripts.seed_data.init_db", new_callable=AsyncMock),
            patch("interntrack.scripts.seed_data.get_db_session", mock_get_db),
        ):
            from interntrack.scripts.seed_data import seed_database

            await seed_database()

        app_calls = [
            c
            for c in mock_session.add.call_args_list
            if c[0][0].__class__.__name__ == "Application"
        ]

        statuses = [c[0][0].status for c in app_calls]
        assert ApplicationStatus.SAVED in statuses
        assert ApplicationStatus.APPLIED in statuses
        assert ApplicationStatus.INTERVIEW in statuses

    @pytest.mark.asyncio
    async def test_seed_database_sample_jobs_data(self):
        """Test SAMPLE_JOBS contains expected data."""
        from interntrack.scripts.seed_data import SAMPLE_JOBS

        assert len(SAMPLE_JOBS) == 8

        titles = [j["title"] for j in SAMPLE_JOBS]
        assert "Senior Python Developer" in titles
        assert "Frontend React Developer" in titles
        assert "Junior Backend Engineer" in titles
        assert "DevOps Engineer" in titles

    @pytest.mark.asyncio
    async def test_seed_database_sample_skills_data(self):
        """Test SAMPLE_SKILLS contains expected data."""
        from interntrack.scripts.seed_data import SAMPLE_SKILLS

        assert len(SAMPLE_SKILLS) == 20

        names = [s["name"] for s in SAMPLE_SKILLS]
        assert "python" in names
        assert "javascript" in names
        assert "docker" in names
        assert "kubernetes" in names
