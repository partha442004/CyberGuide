"""
Unit tests for DeduplicationEngine.
"""

from unittest.mock import AsyncMock

import pytest

from interntrack.domain.models import Job
from interntrack.engines.deduplication import DeduplicationEngine


class TestDeduplicationEngine:
    """Tests for DeduplicationEngine."""

    @pytest.mark.asyncio
    async def test_get_by_url_tolerates_duplicate_rows(self):
        """Duplicate URL rows must not raise MultipleResultsFound.

        Regression: the same posting can be saved by several sources under
        one URL (e.g. the PC discovery CLI + the search-engine net), so
        ``scalar_one_or_none`` used to raise on the first duplicate and
        turn the dedup check into a 500. ``first()`` must win.
        """
        from unittest.mock import AsyncMock

        from interntrack.repositories.job_repository import JobRepository

        class _Scalars:
            def first(self):
                return "first-job"

        class _Result:
            def scalars(self):
                return _Scalars()

        session = AsyncMock()
        session.execute.return_value = _Result()
        repo = JobRepository(session)
        found = await repo.get_by_url("https://example.com/job/dup")
        assert found == "first-job"

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_job_repo(self):
        """Mock job repository."""
        repo = AsyncMock()
        repo.get_by_url.return_value = None
        repo.find_duplicate.return_value = None
        return repo

    @pytest.fixture
    def engine(self, mock_session, mock_job_repo):
        """Create DeduplicationEngine with mocked dependencies."""
        engine = DeduplicationEngine(mock_session)
        engine.job_repo = mock_job_repo
        return engine

    @pytest.mark.asyncio
    async def test_filter_unique_returns_unique_jobs(self, engine, mock_job_repo):
        """Test that filter_unique returns only unique jobs."""
        mock_job_repo.get_by_url.return_value = None

        jobs = [
            {"title": "Job 1", "company": "C1", "url": "https://example.com/1"},
            {"title": "Job 2", "company": "C2", "url": "https://example.com/2"},
            {"title": "Job 3", "company": "C3", "url": "https://example.com/3"},
        ]

        result = await engine.filter_unique(jobs)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_filter_unique_removes_duplicates(self, engine, mock_job_repo):
        """Test that filter_unique removes duplicate jobs."""
        # First job is new, second and third are duplicates
        mock_job_repo.get_by_url.side_effect = [None, Job(id="existing")]

        jobs = [
            {"title": "Job 1", "company": "C1", "url": "https://example.com/1"},
            {"title": "Job 2", "company": "C2", "url": "https://existing.com"},
        ]

        result = await engine.filter_unique(jobs)

        assert len(result) == 1

    def test_compute_hash_same_data(self, engine):
        """Test that compute_hash returns same hash for same data."""
        job1 = {"title": "Test", "company": "Company", "url": "https://example.com"}
        job2 = {"title": "Test", "company": "Company", "url": "https://example.com"}

        hash1 = engine._compute_hash(job1)
        hash2 = engine._compute_hash(job2)

        assert hash1 == hash2

    def test_compute_hash_different_data(self, engine):
        """Test that compute_hash returns different hash for different data."""
        job1 = {"title": "Job 1", "company": "C1", "url": "https://example.com/1"}
        job2 = {"title": "Job 2", "company": "C2", "url": "https://example.com/2"}

        hash1 = engine._compute_hash(job1)
        hash2 = engine._compute_hash(job2)

        assert hash1 != hash2

    def test_calculate_similarity_identical(self, engine):
        """Test similarity calculation for identical jobs."""
        job1 = {
            "title": "Python Developer",
            "company": "TechCorp",
            "url": "https://example.com/1",
        }
        job2 = {
            "title": "Python Developer",
            "company": "TechCorp",
            "url": "https://example.com/1",
        }

        similarity = engine.calculate_similarity(job1, job2)

        assert similarity == 1.0

    def test_calculate_similarity_different(self, engine):
        """Test similarity calculation for different jobs."""
        job1 = {
            "title": "Python Developer",
            "company": "TechCorp",
            "url": "https://example.com/1",
        }
        job2 = {
            "title": "Java Developer",
            "company": "OtherCorp",
            "url": "https://different.com/2",
        }

        similarity = engine.calculate_similarity(job1, job2)

        assert 0.0 <= similarity <= 1.0

    def test_normalize_url(self, engine):
        """Test URL normalization."""
        url1 = "https://WWW.Example.COM/job/1/"
        url2 = "example.com/job/1"

        normalized1 = engine._normalize_url(url1)
        normalized2 = engine._normalize_url(url2)

        assert normalized1 == normalized2
