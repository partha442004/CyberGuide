"""
Unit Tests for the skills API (extended) and domain exceptions.

Covers the real-DB paths of the demand / match / learning-path endpoints in
``interntrack/api/v1/skills.py`` and the remaining exception subclasses in
``interntrack/domain/exceptions.py``.
"""

from unittest.mock import MagicMock

import pytest

from interntrack.api.v1.skills import get_learning_path, get_skill_demand, match_skills
from interntrack.domain.exceptions import (
    ConfigurationError,
    NotificationError,
    ScrapingError,
    ValidationError,
)


class TestSkillsApiRealDb:
    """Tests for the skills endpoints against the in-memory test DB."""

    @pytest.mark.asyncio
    async def test_get_skill_demand_with_empty_db(self, db_session):
        """Should return an empty demand summary on an empty database."""
        result = await get_skill_demand(db=db_session)
        assert isinstance(result, list)
        assert result == []

    @pytest.mark.asyncio
    async def test_match_skills(self, db_session):
        """Should match job skills against user skills."""
        result = await match_skills(
            job_skills=["python", "aws"],
            user_skills=["python"],
            db=db_session,
        )
        assert result["matched_skills"] == ["python"]
        assert result["missing_skills"] == ["aws"]
        assert result["match_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_get_learning_path_without_ai(self, db_session, monkeypatch):
        """Should return an empty path when no AI service is configured."""
        import interntrack.services.ai_service as ai_module

        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_settings.ollama_base_url = None
        monkeypatch.setattr(ai_module, "settings", mock_settings)

        result = await get_learning_path(
            current_skills=["python"],
            target_role="Security Engineer",
            db=db_session,
        )
        assert result == {"steps": [], "message": "AI service not configured"}


class TestRemainingDomainExceptions:
    """Tests for the exception subclasses not yet constructed anywhere."""

    def test_scraping_error(self):
        exc = ScrapingError("linkedin", "blocked")
        assert exc.code == "SCRAPING_ERROR"
        assert exc.status == 422
        assert exc.details == {"source": "linkedin", "reason": "blocked"}
        assert "Scraping failed for linkedin: blocked" in str(exc)

    def test_validation_error(self):
        exc = ValidationError("email", "invalid format")
        assert exc.code == "VALIDATION_ERROR"
        assert exc.status == 422
        assert exc.details == {"field": "email", "reason": "invalid format"}
        assert "Validation failed for email: invalid format" in str(exc)

    def test_configuration_error(self):
        exc = ConfigurationError("DATABASE_URL", "not set")
        assert exc.code == "CONFIGURATION_ERROR"
        assert exc.status == 500
        assert exc.details == {"setting": "DATABASE_URL", "reason": "not set"}
        assert "Configuration error for DATABASE_URL: not set" in str(exc)

    def test_notification_error(self):
        exc = NotificationError("telegram", "timeout")
        assert exc.code == "NOTIFICATION_ERROR"
        assert exc.status == 502
        assert exc.details == {"channel": "telegram", "reason": "timeout"}
