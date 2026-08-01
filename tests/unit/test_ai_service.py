"""Unit tests for services/ai_service.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
            "title": "Security Analyst",
            "company": "Tech Corp",
            "description": "Python security role",
        }
        prompt = service._build_classification_prompt(job_data)

        assert "Security Analyst" in prompt
        assert "Tech Corp" in prompt
        assert "Python security role" in prompt

    @pytest.mark.asyncio
    async def test_classify_with_rules_intern(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = service._classify_with_rules({
            "title": "Cybersecurity Intern",
            "description": "Summer internship",
        })

        assert result["job_type"] == "internship"
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_classify_with_rules_senior(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = service._classify_with_rules({
            "title": "Senior Security Engineer",
            "description": "Remote position",
        })

        assert result["experience_level"] == "senior"
        assert result["is_remote"] is True

    @pytest.mark.asyncio
    async def test_classify_with_rules_junior(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = service._classify_with_rules({
            "title": "Junior SOC Analyst",
            "description": "Entry level",
        })

        assert result["experience_level"] == "junior"

    @pytest.mark.asyncio
    async def test_classify_with_rules_unknown(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = service._classify_with_rules({
            "title": "Security Consultant",
            "description": "General role",
        })

        assert result["job_type"] == "unknown"
        assert result["experience_level"] == "unknown"

    @pytest.mark.asyncio
    async def test_classify_job_fallback_to_rules(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        with patch("interntrack.services.ai_service.settings") as mock_settings:
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = None

            result = await service.classify_job({
                "title": "Intern",
                "description": "Test",
            })

            assert result["job_type"] == "internship"

    @pytest.mark.asyncio
    async def test_match_skills(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)
        service.skill_repo.get_by_name = AsyncMock(return_value=None)

        result = await service.match_skills(
            job_skills=["python", "sql", "docker"],
            user_skills=["python", "sql"],
        )

        assert result["match_percentage"] > 0
        assert "python" in result["matched_skills"]
        assert "docker" in result["missing_skills"]

    @pytest.mark.asyncio
    async def test_match_skills_empty_job_skills(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = await service.match_skills(
            job_skills=[],
            user_skills=["python"],
        )

        assert result["match_percentage"] == 0

    @pytest.mark.asyncio
    async def test_generate_learning_path_no_ai(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        with patch("interntrack.services.ai_service.settings") as mock_settings:
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = None

            result = await service.generate_learning_path(
                current_skills=["python"],
                target_role="Security Engineer",
            )

            assert result["steps"] == []
            assert "not configured" in result["message"]

    @pytest.mark.asyncio
    async def test_classify_with_ollama_failure(self):
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        with patch("interntrack.services.ai_service.settings") as mock_settings:
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "llama3"

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await service.classify_job({
                    "title": "Test",
                    "description": "Test",
                })

                assert "error" in result
