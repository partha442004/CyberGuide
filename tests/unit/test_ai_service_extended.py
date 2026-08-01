"""Extended unit tests for services/ai_service.py.

Covers Ollama, recommendations, rules.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAIServiceClassifyWithOllama:
    """Tests for _classify_with_ollama success and failure paths."""

    def _make_ollama_mock(self, status_code=200, response_json=None):
        """Create mock httpx module for Ollama tests."""
        if response_json is None:
            response_json = {
                "response": '{"job_type": "internship", "confidence": 0.7}',
            }

        fake_response = MagicMock()
        fake_response.status_code = status_code
        fake_response.json.return_value = response_json

        fake_client = AsyncMock()
        fake_client.post.return_value = fake_response

        fake_cm = AsyncMock()
        fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
        fake_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = fake_cm

        return fake_httpx

    @pytest.mark.asyncio
    async def test_classify_with_ollama_success(self):
        """Test Ollama classification succeeds."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        fake_httpx = self._make_ollama_mock()

        with (
            patch.dict("sys.modules", {"httpx": fake_httpx}),
            patch("interntrack.services.ai_service.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "llama3"

            result = await service._classify_with_ollama("test prompt")

        assert result["job_type"] == "internship"
        assert result["confidence"] == 0.7

    @pytest.mark.asyncio
    async def test_classify_with_ollama_non_200_response(self):
        """Test Ollama returns error when status is not 200."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        fake_httpx = self._make_ollama_mock(status_code=500)

        with (
            patch.dict("sys.modules", {"httpx": fake_httpx}),
            patch("interntrack.services.ai_service.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "llama3"

            result = await service._classify_with_ollama("test prompt")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_classify_job_routes_to_ollama(self):
        """Test classify_job routes to Ollama when base URL is set."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        fake_httpx = self._make_ollama_mock(
            response_json={"response": '{"job_type": "full_time", "confidence": 0.8}'},
        )

        with (
            patch.dict("sys.modules", {"httpx": fake_httpx}),
            patch("interntrack.services.ai_service.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "llama3"

            result = await service.classify_job(
                {"title": "Python Dev", "description": "Python role"},
            )

        assert result["job_type"] == "full_time"

    @pytest.mark.asyncio
    async def test_generate_learning_path_with_ollama(self):
        """Test generate_learning_path uses Ollama when configured."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "response": '{"steps": ["step 1", "step 2"]}',
        }
        fake_client = AsyncMock()
        fake_client.post.return_value = fake_response
        fake_cm = AsyncMock()
        fake_cm.__aenter__ = AsyncMock(return_value=fake_client)
        fake_cm.__aexit__ = AsyncMock(return_value=False)
        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = fake_cm

        with (
            patch.dict("sys.modules", {"httpx": fake_httpx}),
            patch("interntrack.services.ai_service.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_model = "llama3"

            result = await service.generate_learning_path(
                current_skills=["python"],
                target_role="Security Engineer",
            )

        assert "steps" in result
        assert len(result["steps"]) == 2


class TestAIServiceSkillRecommendations:
    """Tests for _get_skill_recommendations with real skill data."""

    @pytest.mark.asyncio
    async def test_get_recommendations_with_resources(self):
        """Test recommendations returned when skill has learning_resources."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        mock_skill = MagicMock()
        mock_skill.category.value = "programming"
        mock_skill.learning_resources = [
            "https://course1.com",
            "https://course2.com",
            "https://course3.com",
            "https://course4.com",
        ]

        service.skill_repo.get_by_name = AsyncMock(return_value=mock_skill)

        result = await service._get_skill_recommendations(["python"])

        assert len(result) == 1
        assert result[0]["skill"] == "python"
        assert result[0]["category"] == "programming"
        assert len(result[0]["resources"]) == 3  # max 3

    @pytest.mark.asyncio
    async def test_get_recommendations_no_skill_found(self):
        """Test empty recommendations when skill not found."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        service.skill_repo.get_by_name = AsyncMock(return_value=None)

        result = await service._get_skill_recommendations(["nonexistent"])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_recommendations_no_resources(self):
        """Test empty recommendations when skill has no learning_resources."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        mock_skill = MagicMock()
        mock_skill.learning_resources = []

        service.skill_repo.get_by_name = AsyncMock(return_value=mock_skill)

        result = await service._get_skill_recommendations(["python"])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_recommendations_multiple_skills(self):
        """Test recommendations for multiple skills."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        def mock_get_by_name(name):
            skill = MagicMock()
            skill.category.value = "tool"
            skill.learning_resources = [f"https://{name}.com"]
            return skill

        service.skill_repo.get_by_name = AsyncMock(side_effect=mock_get_by_name)

        result = await service._get_skill_recommendations(
            ["python", "docker", "kubernetes"],
        )

        assert len(result) == 3
        names = [r["skill"] for r in result]
        assert "python" in names
        assert "docker" in names
        assert "kubernetes" in names


class TestAIServiceClassifyRulesLead:
    """Tests for rule-based classification with 'lead' keyword."""

    def test_classify_with_rules_lead(self):
        """Test rule-based classification detects 'lead' as senior."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = service._classify_with_rules(
            {
                "title": "Tech Lead Engineer",
                "description": "Lead a team of developers",
            },
        )

        assert result["experience_level"] == "senior"
        assert result["job_type"] == "unknown"
        assert result["is_remote"] is False

    def test_classify_with_rules_remote_description(self):
        """Test rule-based classification detects remote in description."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        result = service._classify_with_rules(
            {
                "title": "Software Engineer",
                "description": "This is a remote position",
            },
        )

        assert result["is_remote"] is True

    @pytest.mark.asyncio
    async def test_classify_job_no_ai_returns_rules(self):
        """Test classify_job returns rules when no AI configured."""
        from interntrack.services.ai_service import AIService

        session = AsyncMock()
        service = AIService(session)

        with patch("interntrack.services.ai_service.settings") as mock_settings:
            mock_settings.gemini_api_key = None
            mock_settings.ollama_base_url = None

            result = await service.classify_job(
                {
                    "title": "Senior Engineer",
                    "description": "Remote work available",
                },
            )

        assert result["experience_level"] == "senior"
        assert result["is_remote"] is True
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_learning_path_no_ai(self):
        """Test generate_learning_path returns fallback with no AI."""
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
