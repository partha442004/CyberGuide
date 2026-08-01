"""Unit tests for services/learning_service.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestLearningService:
    """Tests for LearningService class."""

    def test_init(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        assert service.session == session
        assert service.skill_repo is not None
        assert service.ai_service is not None

    def test_get_readiness_level_excellent(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        assert service._get_readiness_level(100) == "excellent"
        assert service._get_readiness_level(80) == "excellent"
        assert service._get_readiness_level(85) == "excellent"

    def test_get_readiness_level_good(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        assert service._get_readiness_level(60) == "good"
        assert service._get_readiness_level(70) == "good"
        assert service._get_readiness_level(79) == "good"

    def test_get_readiness_level_moderate(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        assert service._get_readiness_level(40) == "moderate"
        assert service._get_readiness_level(50) == "moderate"
        assert service._get_readiness_level(59) == "moderate"

    def test_get_readiness_level_needs_improvement(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        assert service._get_readiness_level(0) == "needs_improvement"
        assert service._get_readiness_level(20) == "needs_improvement"
        assert service._get_readiness_level(39) == "needs_improvement"

    @pytest.mark.asyncio
    async def test_get_learning_paths_no_filter(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(id="1", name="Python Basics"),
            MagicMock(id="2", name="Advanced Python"),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await service.get_learning_paths()

        assert len(result) == 2
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_learning_paths_with_skill_id(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(id="1", name="Python Basics"),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await service.get_learning_paths(skill_id="skill_123")

        assert len(result) == 1
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_learning_path(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        data = {
            "name": "Python for Beginners",
            "description": "Learn Python from scratch",
            "platform": "udemy",
            "estimated_hours": 20,
            "difficulty_level": "beginner",
        }

        await service.create_learning_path(data)

        session.add.assert_called_once()
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        user_skills = ["python", "django", "postgresql"]
        job_skills = ["python", "django", "redis", "docker"]

        result = await service.get_skill_gap_analysis(user_skills, job_skills)

        assert "python" in result["matched_skills"]
        assert "django" in result["matched_skills"]
        assert "redis" in result["missing_skills"]
        assert "docker" in result["missing_skills"]
        assert result["match_percentage"] == 50.0
        assert result["readiness_level"] == "moderate"

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis_perfect_match(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        user_skills = ["python", "django"]
        job_skills = ["python", "django"]

        result = await service.get_skill_gap_analysis(user_skills, job_skills)

        assert result["match_percentage"] == 100.0
        assert result["readiness_level"] == "excellent"
        assert len(result["missing_skills"]) == 0

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis_no_match(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        user_skills = ["java", "spring"]
        job_skills = ["python", "django"]

        result = await service.get_skill_gap_analysis(user_skills, job_skills)

        assert result["match_percentage"] == 0.0
        assert result["readiness_level"] == "needs_improvement"
        assert "python" in result["missing_skills"]
        assert "django" in result["missing_skills"]

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis_empty_job_skills(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        result = await service.get_skill_gap_analysis(["python"], [])

        assert result["match_percentage"] == 0.0
        assert result["readiness_level"] == "needs_improvement"

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis_extra_skills(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        user_skills = ["python", "django", "redis", "docker"]
        job_skills = ["python", "django"]

        result = await service.get_skill_gap_analysis(user_skills, job_skills)

        assert result["match_percentage"] == 100.0
        assert "redis" in result["extra_skills"]
        assert "docker" in result["extra_skills"]

    @pytest.mark.asyncio
    async def test_get_platform_resources(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        mock_path = MagicMock()
        mock_path.id = "1"
        mock_path.name = "Python Course"
        mock_path.description = "Learn Python"
        mock_path.estimated_hours = 20
        mock_path.difficulty_level = "beginner"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_path]
        session.execute = AsyncMock(return_value=mock_result)

        result = await service.get_platform_resources("udemy")

        assert len(result) == 1
        assert result[0]["name"] == "Python Course"
        assert result[0]["estimated_hours"] == 20

    @pytest.mark.asyncio
    async def test_get_recommendations(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        # Mock AI service
        service.ai_service.generate_learning_path = AsyncMock(
            return_value={
                "skills": ["python"],
                "steps": ["Step 1: Learn Python"],
            },
        )

        # Mock skill repo
        mock_skill = MagicMock()
        mock_skill.name = "python"
        mock_skill.category.value = "programming"
        mock_skill.learning_resources = ["https://example.com/python"]
        service.skill_repo.get_by_name = AsyncMock(return_value=mock_skill)

        result = await service.get_recommendations(
            ["javascript"],
            "Python Developer",
        )

        assert result["target_role"] == "Python Developer"
        assert "python" in result["missing_skills"]
        assert len(result["recommendations"]) == 1
        assert len(result["learning_path"]) == 1

    @pytest.mark.asyncio
    async def test_get_recommendations_no_resources(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        # Mock AI service
        service.ai_service.generate_learning_path = AsyncMock(
            return_value={
                "skills": ["python"],
                "steps": [],
            },
        )

        # Mock skill repo returning None
        service.skill_repo.get_by_name = AsyncMock(return_value=None)

        result = await service.get_recommendations(
            ["javascript"],
            "Python Developer",
        )

        assert result["target_role"] == "Python Developer"
        assert len(result["recommendations"]) == 0
