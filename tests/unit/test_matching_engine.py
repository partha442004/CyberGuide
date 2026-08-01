"""Unit tests for engines/matching.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMatchingEngineHelpers:
    """Tests for MatchingEngine helper methods."""

    def _make_engine(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        return MatchingEngine(session)

    def test_get_readiness_level_excellent(self):
        engine = self._make_engine()
        assert engine._get_readiness_level(85) == "excellent"
        assert engine._get_readiness_level(100) == "excellent"

    def test_get_readiness_level_good(self):
        engine = self._make_engine()
        assert engine._get_readiness_level(65) == "good"
        assert engine._get_readiness_level(79) == "good"

    def test_get_readiness_level_moderate(self):
        engine = self._make_engine()
        assert engine._get_readiness_level(45) == "moderate"
        assert engine._get_readiness_level(59) == "moderate"

    def test_get_readiness_level_needs_improvement(self):
        engine = self._make_engine()
        assert engine._get_readiness_level(10) == "needs_improvement"
        assert engine._get_readiness_level(0) == "needs_improvement"

    def test_get_skill_priority_high(self):
        engine = self._make_engine()
        assert engine._get_skill_priority("python", "programming") == 3
        assert engine._get_skill_priority("javascript", "programming") == 3
        assert engine._get_skill_priority("sql", "tool") == 3
        assert engine._get_skill_priority("git", "tool") == 3
        assert engine._get_skill_priority("rest api", "framework") == 3

    def test_get_skill_priority_medium(self):
        engine = self._make_engine()
        assert engine._get_skill_priority("docker", "tool") == 2
        assert engine._get_skill_priority("react", "framework") == 2
        assert engine._get_skill_priority("aws", "tool") == 2
        assert engine._get_skill_priority("kubernetes", "tool") == 2
        assert engine._get_skill_priority("unknown_lang", "programming") == 2

    def test_get_skill_priority_low(self):
        engine = self._make_engine()
        assert engine._get_skill_priority("figma", "tool") == 1
        assert engine._get_skill_priority("communication", "soft_skill") == 1

    def test_get_default_resources_python(self):
        engine = self._make_engine()
        resources = engine._get_default_resources("python")
        assert len(resources) == 2
        assert any("python" in r["name"].lower() for r in resources)

    def test_get_default_resources_javascript(self):
        engine = self._make_engine()
        resources = engine._get_default_resources("javascript")
        assert len(resources) == 2
        assert any("javascript" in r["name"].lower() for r in resources)

    def test_get_default_resources_react(self):
        engine = self._make_engine()
        resources = engine._get_default_resources("react")
        assert len(resources) == 2

    def test_get_default_resources_docker(self):
        engine = self._make_engine()
        resources = engine._get_default_resources("docker")
        assert len(resources) == 2

    def test_get_default_resources_sql(self):
        engine = self._make_engine()
        resources = engine._get_default_resources("sql")
        assert len(resources) == 2

    def test_get_default_resources_unknown(self):
        engine = self._make_engine()
        resources = engine._get_default_resources("kubernetes")
        assert len(resources) == 1
        assert "kubernetes" in resources[0]["url"].lower()

    @pytest.mark.asyncio
    async def test_get_skills_for_role_backend(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("backend developer")
        assert "python" in skills
        assert "javascript" in skills
        assert "sql" in skills
        assert "docker" in skills

    @pytest.mark.asyncio
    async def test_get_skills_for_role_frontend(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("frontend developer")
        assert "javascript" in skills
        assert "react" in skills
        assert "html" in skills

    @pytest.mark.asyncio
    async def test_get_skills_for_role_fullstack(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("full stack developer")
        assert "python" in skills
        assert "react" in skills
        assert "docker" in skills

    @pytest.mark.asyncio
    async def test_get_skills_for_role_data_scientist(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("data scientist")
        assert "python" in skills
        assert "machine learning" in skills
        assert "tensorflow" in skills

    @pytest.mark.asyncio
    async def test_get_skills_for_role_devops(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("devops engineer")
        assert "docker" in skills
        assert "kubernetes" in skills
        assert "aws" in skills
        assert "terraform" in skills

    @pytest.mark.asyncio
    async def test_get_skills_for_role_unknown(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("random role xyz")
        assert "python" in skills
        assert "git" in skills

    @pytest.mark.asyncio
    async def test_get_skills_for_role_mobile(self):
        engine = self._make_engine()
        skills = await engine._get_skills_for_role("mobile developer")
        assert "swift" in skills
        assert "kotlin" in skills
        assert "react native" in skills


class TestMatchingEngineAsync:
    """Tests for MatchingEngine async methods."""

    @pytest.mark.asyncio
    async def test_find_matching_jobs_empty_user_skills(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        engine = MatchingEngine(session)

        # Mock empty user skills
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        result = await engine.find_matching_jobs("user-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        engine = MatchingEngine(session)

        # Mock user skills
        user_result = MagicMock()
        user_result.all.return_value = [
            (MagicMock(lower=lambda: "python"), MagicMock(value="programming")),
        ]
        session.execute.return_value = user_result

        result = await engine.get_skill_gap_analysis("user-1", "backend developer")

        assert "target_role" in result
        assert "matched_skills" in result
        assert "missing_skills" in result
        assert "readiness_level" in result
        assert result["target_role"] == "backend developer"
