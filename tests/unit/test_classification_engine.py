"""Unit tests for engines/classification.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


class TestClassificationEngine:
    """Tests for ClassificationEngine class."""

    def test_init(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        assert engine.session == session
        assert engine.skill_repo is not None
        assert engine.ai_service is not None

    def test_categorize_skill_programming(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import SkillCategory

        session = AsyncMock()
        engine = ClassificationEngine(session)

        assert engine._categorize_skill("python") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("javascript") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("typescript") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("java") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("go") == SkillCategory.PROGRAMMING

    def test_categorize_skill_framework(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import SkillCategory

        session = AsyncMock()
        engine = ClassificationEngine(session)

        assert engine._categorize_skill("react") == SkillCategory.FRAMEWORK
        assert engine._categorize_skill("vue") == SkillCategory.FRAMEWORK
        assert engine._categorize_skill("django") == SkillCategory.FRAMEWORK
        assert engine._categorize_skill("flask") == SkillCategory.FRAMEWORK
        assert engine._categorize_skill("fastapi") == SkillCategory.FRAMEWORK

    def test_categorize_skill_tool(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import SkillCategory

        session = AsyncMock()
        engine = ClassificationEngine(session)

        assert engine._categorize_skill("docker") == SkillCategory.TOOL
        assert engine._categorize_skill("kubernetes") == SkillCategory.TOOL
        assert engine._categorize_skill("aws") == SkillCategory.TOOL
        assert engine._categorize_skill("git") == SkillCategory.TOOL
        assert engine._categorize_skill("linux") == SkillCategory.TOOL

    def test_categorize_skill_soft_skill(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import SkillCategory

        session = AsyncMock()
        engine = ClassificationEngine(session)

        assert engine._categorize_skill("communication") == SkillCategory.SOFT_SKILL
        assert engine._categorize_skill("leadership") == SkillCategory.SOFT_SKILL
        assert engine._categorize_skill("teamwork") == SkillCategory.SOFT_SKILL

    def test_extract_skills_from_text(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        text = "We need a Python developer with Django and PostgreSQL experience. Docker and AWS are pluses."

        skills = engine._extract_skills_from_text(text)

        assert "python" in skills
        assert "django" in skills
        assert "postgresql" in skills
        assert "docker" in skills
        assert "aws" in skills

    def test_extract_skills_from_text_no_match(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        text = "We need a good communicator."

        skills = engine._extract_skills_from_text(text)

        assert len(skills) == 0

    def test_extract_skills_from_text_duplicates(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        text = "Python and python and PYTHON are the same."

        skills = engine._extract_skills_from_text(text)

        assert skills.count("python") == 1

    def test_rule_based_classify_internship(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import JobType

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Python Intern",
            "description": "Join our team.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["job_type"] == JobType.INTERNSHIP.value

    def test_rule_based_classify_remote(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import JobType

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Software Engineer",
            "description": "Remote work available.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["is_remote"] is True

    def test_rule_based_classify_contract(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import JobType

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Contract Developer",
            "description": "Short-term contract.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["job_type"] == JobType.CONTRACT.value

    def test_rule_based_classify_senior(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import ExperienceLevel

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Senior Developer",
            "description": "Lead our team.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["experience_level"] == ExperienceLevel.SENIOR.value

    def test_rule_based_classify_junior(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import ExperienceLevel

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Junior Developer",
            "description": "Entry level position.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["experience_level"] == ExperienceLevel.JUNIOR.value

    def test_rule_based_classify_mid(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import ExperienceLevel

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Mid-level Developer",
            "description": "Some experience required.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["experience_level"] == ExperienceLevel.MID.value

    def test_rule_based_classify_unknown(self):
        from interntrack.engines.classification import ClassificationEngine
        from interntrack.domain.enums import JobType, ExperienceLevel

        session = AsyncMock()
        engine = ClassificationEngine(session)

        job_data = {
            "title": "Developer",
            "description": "Some description.",
        }

        result = engine._rule_based_classify(job_data)

        assert result["job_type"] == JobType.UNKNOWN.value
        assert result["experience_level"] == ExperienceLevel.UNKNOWN.value

    @pytest.mark.asyncio
    async def test_classify_job_ai_success(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        # Mock AI service
        engine.ai_service.classify_job = AsyncMock(return_value={
            "job_type": "full_time",
            "experience_level": "mid",
            "skills": ["python", "django"],
            "is_remote": False,
            "confidence": 0.9,
        })

        # Mock skill repo
        mock_skill = MagicMock()
        mock_skill.id = 1
        mock_skill.name = "python"
        mock_skill.category.value = "programming"
        engine.skill_repo.create_or_get = AsyncMock(return_value=mock_skill)

        job_data = {
            "title": "Python Developer",
            "description": "We need a Python developer.",
        }

        result = await engine.classify_job(job_data)

        assert result["job_type"] == "full_time"
        assert result["confidence"] == 0.9
        assert "matched_skills" in result

    @pytest.mark.asyncio
    async def test_classify_job_ai_fallback_to_rules(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        # Mock AI service to return error
        engine.ai_service.classify_job = AsyncMock(return_value={"error": "AI failed"})

        job_data = {
            "title": "Python Intern",
            "description": "Internship position.",
        }

        result = await engine.classify_job(job_data)

        # Should fall back to rule-based classification
        assert "job_type" in result
        assert "experience_level" in result
