"""
Unit Tests for AIService Gemini paths.

Covers ``_classify_with_gemini`` (success + failure) and the
``classify_job``/``generate_learning_path`` routing to Gemini.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.services.ai_service import AIService


def fake_google_modules(genai_mock):
    """Return a sys.modules patch dict faking the google package tree."""
    import types

    google_pkg = types.ModuleType("google")
    google_pkg.__path__ = []  # namespace-like so submodule import works
    return {"google": google_pkg, "google.generativeai": genai_mock}


@pytest.fixture
def gemini_settings(monkeypatch):
    """Point the service settings at a fake gemini_api_key."""
    import interntrack.services.ai_service as ai_module

    mock_settings = MagicMock()
    mock_settings.gemini_api_key = "fake-key"
    mock_settings.gemini_model = "gemini-pro"
    monkeypatch.setattr(ai_module, "settings", mock_settings)
    return mock_settings


class TestClassifyWithGemini:
    """Tests for the Gemini classification path."""

    @pytest.mark.asyncio
    async def test_success_parses_json(self, gemini_settings):
        """Should return parsed JSON from the model response."""
        fake_genai = MagicMock()
        model = MagicMock()
        model.generate_content.return_value.text = json.dumps(
            {"job_type": "full_time", "confidence": 0.9}
        )
        fake_genai.GenerativeModel.return_value = model

        with patch.dict("sys.modules", fake_google_modules(fake_genai)):
            service = AIService(session=MagicMock())
            result = await service._classify_with_gemini("some prompt")

        assert result == {"job_type": "full_time", "confidence": 0.9}
        fake_genai.configure.assert_called_once_with(api_key="fake-key")
        model.generate_content.assert_called_once_with("some prompt")

    @pytest.mark.asyncio
    async def test_failure_returns_error(self, gemini_settings):
        """Should return an error dict when the API raises."""
        fake_genai = MagicMock()
        fake_genai.configure.side_effect = RuntimeError("api down")

        with patch.dict("sys.modules", fake_google_modules(fake_genai)):
            service = AIService(session=MagicMock())
            result = await service._classify_with_gemini("prompt")

        assert result == {"error": "Gemini classification failed"}

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self, gemini_settings):
        """Should return an error dict when the response is not valid JSON."""
        fake_genai = MagicMock()
        model = MagicMock()
        model.generate_content.return_value.text = "{not-json"
        fake_genai.GenerativeModel.return_value = model

        with patch.dict("sys.modules", fake_google_modules(fake_genai)):
            service = AIService(session=MagicMock())
            result = await service._classify_with_gemini("prompt")

        assert result == {"error": "Gemini classification failed"}


class TestClassifyWithOllamaErrorPath:
    """Tests for the Ollama error path (except branch)."""

    @pytest.mark.asyncio
    async def test_ollama_post_raises_returns_error(self, monkeypatch):
        """Should log and return an error dict when the HTTP call raises."""
        import interntrack.services.ai_service as ai_module

        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "llama3"
        monkeypatch.setattr(ai_module, "settings", mock_settings)

        class FakeResponse:
            status_code = 500

        async def fake_post(url, **kwargs):
            return FakeResponse()

        fake_client = MagicMock()
        fake_client.__aenter__ = AsyncMock()
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = fake_post

        with patch("httpx.AsyncClient", return_value=fake_client):
            service = AIService(session=MagicMock())
            result = await service._classify_with_ollama("prompt")

        assert result == {"error": "Ollama classification failed"}


class TestClassifyJobRouting:
    """Tests for classify_job routing to Gemini."""

    @pytest.mark.asyncio
    async def test_routes_to_gemini_when_key_configured(self, gemini_settings):
        """Should call _classify_with_gemini when gemini_api_key is set."""
        service = AIService(session=MagicMock())
        with patch.object(
            service, "_classify_with_gemini", new=AsyncMock(return_value={"ok": True})
        ) as mock_gemini:
            result = await service.classify_job({"title": "Security Engineer"})

        assert result == {"ok": True}
        mock_gemini.assert_awaited_once()


class TestGenerateLearningPathGemini:
    """Tests for generate_learning_path routing to Gemini."""

    @pytest.mark.asyncio
    async def test_routes_to_gemini(self, gemini_settings):
        """Should call _classify_with_gemini when gemini_api_key is set."""
        service = AIService(session=MagicMock())
        with patch.object(
            service, "_classify_with_gemini", new=AsyncMock(return_value={"steps": []})
        ) as mock_gemini:
            result = await service.generate_learning_path(
                ["python"], "Security Engineer"
            )

        assert result == {"steps": []}
        mock_gemini.assert_awaited_once()
