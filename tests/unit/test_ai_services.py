"""
Tests for AI resume enhancer and job recommender services.
"""

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.services.ai_resume_enhancer import (
    AIResumeEnhancer,
    enhance_resume_parsing,
)
from interntrack.services.job_recommender import JobRecommender


class TestAIResumeEnhancer:
    """Tests for AI resume enhancer."""

    def setup_method(self):
        self.enhancer = AIResumeEnhancer()

    def test_enhance_skill_extraction_basic(self):
        text = """
        Security Engineer with Python and Nmap experience.
        """
        basic_skills = [
            {"name": "Python", "category": "scripting", "confidence": 0.9},
            {"name": "Nmap", "category": "security_tools", "confidence": 0.9},
        ]

        enhanced = self.enhancer.enhance_skill_extraction(text, basic_skills)

        # Should keep basic skills
        names = [s["name"].lower() for s in enhanced]
        assert "python" in names
        assert "nmap" in names

    def test_enhance_skill_extraction_synonyms(self):
        text = "Experience with burp and k8s and infosec"
        basic_skills = []

        enhanced = self.enhancer.enhance_skill_extraction(text, basic_skills)

        names = [s["name"].lower() for s in enhanced]
        # burp -> burp suite, k8s -> kubernetes, infosec -> information security
        assert "burp suite" in names or "burp" in names
        assert "kubernetes" in names
        assert "information security" in names

    def test_extract_experience_level_senior(self):
        text = "Senior Security Engineer with 7+ years of experience"
        assert self.enhancer.extract_experience_level(text) == "senior"

    def test_extract_experience_level_junior(self):
        text = "Fresher with 1 year of experience"
        assert self.enhancer.extract_experience_level(text) == "junior"

    def test_extract_experience_level_mid(self):
        text = "Security Analyst with 3 years of experience"
        assert self.enhancer.extract_experience_level(text) == "mid"

    def test_extract_preferred_roles(self):
        text = "Seeking a SOC Analyst position in cybersecurity"
        roles = self.enhancer.extract_preferred_roles(text)
        assert len(roles) > 0

    def test_enhance_resume_parsing(self):
        text = """
        John Doe - Security Engineer
        Seeking a penetration tester role.

        Skills:
        - Python, Nmap, Metasploit
        - Burp Suite, Wireshark
        """
        basic_skills = [
            {"name": "Python", "category": "scripting", "confidence": 0.9},
            {"name": "Nmap", "category": "security_tools", "confidence": 0.9},
        ]

        result = enhance_resume_parsing(text, basic_skills)
        assert "skills" in result
        assert "experience_level" in result
        assert "preferred_roles" in result
        assert result["total_skills"] >= 2


class TestJobRecommender:
    """Tests for job recommender."""

    def test_init(self):
        session = MagicMock()
        recommender = JobRecommender(session)
        assert recommender.session == session

    @pytest.mark.asyncio
    async def test_get_personalized_recommendations_no_skills(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        # Mock user profile with no skills
        with patch.object(
            recommender,
            "_build_user_profile",
            new=AsyncMock(return_value={"skills": {}}),
        ):
            result = await recommender.get_personalized_recommendations("user1")
            assert result == []

    def test_calculate_location_score_matching(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        job = MagicMock()
        job.location = "Bangalore, India"

        user_profile = {"preferences": {"location": "Bangalore", "remote_only": False}}

        score = recommender._calculate_location_score(job, user_profile, None)
        assert score == 100.0

    def test_calculate_location_score_remote(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        job = MagicMock()
        job.location = "Remote"

        user_profile = {"preferences": {"location": "Bangalore", "remote_only": True}}

        score = recommender._calculate_location_score(job, user_profile, None)
        assert score == 100.0

    def test_extract_job_skills(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        job = MagicMock()
        job.tags = ["python", "security"]
        job.title = "Security Engineer"
        job.description = "Python and AWS experience required"

        skills = recommender._extract_job_skills(job)
        assert "python" in skills
        assert "security" in skills
        assert "aws" in skills

    def test_calculate_recency_score(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        from datetime import datetime, timedelta

        job = MagicMock()
        job.posted_at = datetime.now(UTC) - timedelta(days=1)
        assert recommender._calculate_recency_score(job) == 100.0

        job.posted_at = datetime.now(UTC) - timedelta(days=10)
        assert recommender._calculate_recency_score(job) == 40.0

    def test_get_match_reasons(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        job = MagicMock()
        job.tags = ["python", "security"]
        job.title = "Security Engineer"
        job.location = "Bangalore"

        user_profile = {
            "skills": {"python": {"proficiency": 4}, "security": {"proficiency": 5}},
            "categories": ["security", "programming"],
        }

        reasons = recommender._get_match_reasons(job, user_profile)
        assert len(reasons) > 0

    def test_identify_skill_gaps(self):
        session = MagicMock()
        recommender = JobRecommender(session)

        job = MagicMock()
        job.tags = ["python", "kubernetes"]
        job.title = "DevOps Engineer"
        job.description = ""

        user_profile = {"skills": {"python": {"proficiency": 4}}}

        gaps = recommender._identify_skill_gaps(job, user_profile)
        assert "kubernetes" in gaps
        assert "python" not in gaps
