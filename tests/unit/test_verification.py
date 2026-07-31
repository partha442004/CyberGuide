"""
Unit tests for VerificationEngine.
"""

import pytest
from unittest.mock import AsyncMock

from interntrack.engines.verification import VerificationEngine


class TestVerificationEngine:
    """Tests for VerificationEngine."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def engine(self, mock_session):
        """Create VerificationEngine with mocked dependencies."""
        return VerificationEngine(mock_session)

    @pytest.mark.asyncio
    async def test_verify_job_valid(self, engine):
        """Test verifying a valid job."""
        job_data = {
            "title": "Python Developer",
            "company": "TechCorp",
            "url": "https://example.com/job/1",
        }

        is_valid, issues = await engine.verify_job(job_data)

        assert is_valid is True
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_verify_job_missing_title(self, engine):
        """Test verifying job with missing title."""
        job_data = {
            "company": "TechCorp",
            "url": "https://example.com/job/1",
        }

        is_valid, issues = await engine.verify_job(job_data)

        assert is_valid is False
        assert any("Missing required field: title" in i for i in issues)

    @pytest.mark.asyncio
    async def test_verify_job_missing_company(self, engine):
        """Test verifying job with missing company."""
        job_data = {
            "title": "Python Developer",
            "url": "https://example.com/job/1",
        }

        is_valid, issues = await engine.verify_job(job_data)

        assert is_valid is False
        assert any("Missing required field: company" in i for i in issues)

    @pytest.mark.asyncio
    async def test_verify_job_missing_url(self, engine):
        """Test verifying job with missing URL."""
        job_data = {
            "title": "Python Developer",
            "company": "TechCorp",
        }

        is_valid, issues = await engine.verify_job(job_data)

        assert is_valid is False
        assert any("Missing required field: url" in i for i in issues)

    @pytest.mark.asyncio
    async def test_verify_job_spam_detected(self, engine):
        """Test that spam is detected."""
        job_data = {
            "title": "Make money fast!!!",
            "company": "Unknown",
            "url": "https://example.com/job/1",
            "description": "Work from home and earn $10000 per day!",
        }

        is_valid, issues = await engine.verify_job(job_data)

        assert is_valid is False
        assert any("spam" in i.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_verify_jobs_filters_invalid(self, engine):
        """Test that verify_jobs filters out invalid jobs."""
        jobs = [
            {"title": "Valid Job", "company": "C1", "url": "https://example.com/1"},
            {"title": "", "company": "C2", "url": "https://example.com/2"},  # Missing title
            {"title": "Another Valid", "company": "C3", "url": "https://example.com/3"},
        ]

        valid_jobs, invalid_jobs = await engine.verify_jobs(jobs)

        assert len(valid_jobs) == 2
        assert len(invalid_jobs) == 1

    def test_validate_url_valid(self, engine):
        """Test URL validation with valid URL."""
        issues = engine._validate_url("https://example.com/job/1")

        assert len(issues) == 0

    def test_validate_url_empty(self, engine):
        """Test URL validation with empty URL."""
        issues = engine._validate_url("")

        assert len(issues) > 0

    def test_validate_url_invalid_format(self, engine):
        """Test URL validation with invalid format."""
        issues = engine._validate_url("not-a-url")

        assert len(issues) > 0

    def test_validate_url_too_long(self, engine):
        """Test URL validation with too long URL."""
        long_url = "https://example.com/" + "a" * 2000
        issues = engine._validate_url(long_url)

        assert any("too long" in i.lower() for i in issues)

    def test_validate_salary_min_greater_than_max(self, engine):
        """Test salary validation with min > max."""
        job_data = {"salary_min": 100000, "salary_max": 50000}
        issues = engine._validate_salary(job_data)

        assert len(issues) > 0
