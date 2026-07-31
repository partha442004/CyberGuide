"""Unit tests for services/ai_service.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


class TestAIService:
    """Tests for AIService class."""

    def test_init(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        assert service.session == session
        assert service.skill_repo is not None

    def test_build_classification_prompt(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Python Developer",
            "company": "TechCorp",
            "description": "We need a Python developer with Django experience.",
        }

        prompt = service._build_classification_prompt(job_data)

        assert "Python Developer" in prompt
        assert "TechCorp" in prompt
        assert "Python developer with Django" in prompt

    def test_build_classification_prompt_missing_fields(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        prompt = service._build_classification_prompt({})

        assert "N/A" in prompt

    def test_classify_with_rules_internship(self):
        from interntrack.services.ai_service import AIService
        from interntrack.domain.enums import JobType

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Python Intern",
            "description": "Join our team as an intern.",
        }

        result = service._classify_with_rules(job_data)

        assert result["job_type"] == JobType.INTERNSHIP.value
        assert result["confidence"] == 0.5

    def test_classify_with_rules_remote(self):
        from interntrack.services.ai_service import AIService
        from interntrack.domain.enums import JobType

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Remote Developer",
            "description": "Work from anywhere.",
        }

        result = service._classify_with_rules(job_data)

        assert result["job_type"] == JobType.REMOTE.value
        assert result["is_remote"] is True

    def test_classify_with_rules_senior(self):
        from interntrack.services.ai_service import AIService
        from interntrack.domain.enums import ExperienceLevel

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Senior Python Developer",
            "description": "Looking for experienced developer.",
        }

        result = service._classify_with_rules(job_data)

        assert result["experience_level"] == ExperienceLevel.SENIOR.value

    def test_classify_with_rules_junior(self):
        from interntrack.services.ai_service import AIService
        from interntrack.domain.enums import ExperienceLevel

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Junior Python Developer",
            "description": "Entry level position.",
        }

        result = service._classify_with_rules(job_data)

        assert result["experience_level"] == ExperienceLevel.JUNIOR.value

    def test_classify_with_rules_unknown(self):
        from interntrack.services.ai_service import AIService
        from interntrack.domain.enums import JobType, ExperienceLevel

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Developer",
            "description": "Some description.",
        }

        result = service._classify_with_rules(job_data)

        assert result["job_type"] == JobType.UNKNOWN.value
        assert result["experience_level"] == ExperienceLevel.UNKNOWN.value

    @pytest.mark.asyncio
    @patch("interntrack.services.ai_service.settings")
    async def test_classify_job_fallback_to_rules(self, mock_settings):
        from interntrack.services.ai_service import AIService

        mock_settings.gemini_api_key = None
        mock_settings.ollama_base_url = None

        session = AsyncMock()
        service = AIService(session)

        job_data = {
            "title": "Python Developer",
            "description": "Remote position.",
        }

        result = await service.classify_job(job_data)

        assert "job_type" in result
        assert "experience_level" in result

    @pytest.mark.asyncio
    async def test_match_skills(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)
        service.skill_repo.get_by_name = AsyncMock(return_value=None)

        job_skills = ["python", "django", "postgresql"]
        user_skills = ["python", "javascript"]

        result = await service.match_skills(job_skills, user_skills)

        assert "python" in result["matched_skills"]
        assert "django" in result["missing_skills"]
        assert "postgresql" in result["missing_skills"]
        assert result["match_percentage"] == pytest.approx(33.33, rel=0.01)

    @pytest.mark.asyncio
    async def test_match_skills_empty_job_skills(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)
        service.skill_repo.get_by_name = AsyncMock(return_value=None)

        result = await service.match_skills([], ["python"])

        assert result["match_percentage"] == 0
        assert result["matched_skills"] == []

    @pytest.mark.asyncio
    async def test_match_skills_perfect_match(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)
        service.skill_repo.get_by_name = AsyncMock(return_value=None)

        job_skills = ["python", "django"]
        user_skills = ["python", "django", "javascript"]

        result = await service.match_skills(job_skills, user_skills)

        assert result["match_percentage"] == 100
        assert len(result["missing_skills"]) == 0
