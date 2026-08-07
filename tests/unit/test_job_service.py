"""
Unit tests for JobService.
"""

from unittest.mock import AsyncMock

import pytest

from interntrack.domain.enums import JobSource, JobType
from interntrack.domain.exceptions import DuplicateJobError
from interntrack.domain.models import Job
from interntrack.services.job_service import JobService


class TestJobService:
    """Tests for JobService."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_job_repo(self):
        """Mock job repository."""
        repo = AsyncMock()
        repo.get_by_url.return_value = None
        repo.get_by_id.return_value = None
        repo.find_cross_source_duplicate.return_value = None
        repo.create.return_value = Job(
            id="test-id-123",
            title="Test Job",
            company="Test Company",
            url="https://example.com/job/1",
            source=JobSource.MANUAL,
        )
        return repo

    @pytest.fixture
    def service(self, mock_session, mock_job_repo):
        """Create JobService with mocked dependencies."""
        service = JobService(mock_session)
        service.job_repo = mock_job_repo
        return service

    @pytest.mark.asyncio
    async def test_create_job_success(self, service, mock_job_repo):
        """Test successful job creation."""
        job_data = {
            "title": "Python Developer",
            "company": "TechCorp",
            "url": "https://example.com/job/1",
        }

        result = await service.create_job(job_data)

        assert result is not None
        assert result.title == "Test Job"
        mock_job_repo.create.assert_called_once()

    def test_classify_job_type(self):
        from interntrack.services.job_service import classify_job_type

        assert classify_job_type("Security Intern") == "internship"
        assert classify_job_type("Cybersecurity Fresher Trainee") == "internship"
        assert classify_job_type("SOC Analyst - Part Time") == "part_time"
        assert classify_job_type("Penetration Tester (Contract)") == "contract"
        assert classify_job_type("Freelance VAPT Consultant") == "freelance"
        assert classify_job_type("Senior Security Engineer (Full Time)") == "full_time"
        # No explicit marker -> defaults to full-time (most postings).
        assert classify_job_type("Security Engineer") == "full_time"
        assert classify_job_type("SOC Analyst") == "full_time"

    @pytest.mark.asyncio
    async def test_create_job_infers_job_type(self, service, mock_job_repo):
        """A missing job_type is inferred from the title at save time."""
        await service.create_job(
            {
                "title": "Cybersecurity Intern",
                "company": "SecureCo",
                "url": "https://example.com/intern",
            }
        )

        created = mock_job_repo.create.call_args[0][0]
        assert created.job_type == "internship"

    @pytest.mark.asyncio
    async def test_create_job_keeps_provided_job_type(self, service, mock_job_repo):
        """A scraper-provided job_type is respected."""
        await service.create_job(
            {
                "title": "Security Analyst",
                "company": "SecureCo",
                "url": "https://example.com/analyst",
                "job_type": "full_time",
            }
        )

        created = mock_job_repo.create.call_args[0][0]
        assert created.job_type == "full_time"

    @pytest.mark.asyncio
    async def test_create_job_truncates_overlong_fields(self, service, mock_job_repo):
        """Over-long fields are clamped so Postgres varchar(N) never rejects."""
        job_data = {
            "title": "T" * 600,
            "company": "C" * 300,
            "location": "L" * 300,
            "url": "https://example.com/job/1",
        }

        await service.create_job(job_data)

        created = mock_job_repo.create.call_args[0][0]
        assert len(created.title) == 500
        assert len(created.company) == 200
        assert len(created.location) == 200

    @pytest.mark.asyncio
    async def test_create_job_duplicate_url(self, service, mock_job_repo):
        """Test that duplicate URL raises DuplicateJobError."""
        mock_job_repo.get_by_url.return_value = Job(id="existing")

        job_data = {
            "title": "Duplicate Job",
            "company": "TechCorp",
            "url": "https://example.com/existing",
        }

        with pytest.raises(DuplicateJobError):
            await service.create_job(job_data)

    @pytest.mark.asyncio
    async def test_create_job_cross_source_duplicate(self, service, mock_job_repo):
        """Same posting from another board (different URL) is rejected."""
        mock_job_repo.get_by_url.return_value = None
        mock_job_repo.find_cross_source_duplicate.return_value = Job(id="other")

        job_data = {
            "title": "Penetration Tester",
            "company": "Brillio",
            "url": "https://linkedin.com/jobs/other-source",
        }

        with pytest.raises(DuplicateJobError):
            await service.create_job(job_data)

    @pytest.mark.asyncio
    async def test_create_job_passes_title_company_to_dedup(
        self, service, mock_job_repo
    ):
        """The cross-source check receives the normalized job title+company."""
        mock_job_repo.get_by_url.return_value = None
        mock_job_repo.find_cross_source_duplicate.return_value = None

        await service.create_job(
            {
                "title": "SOC Analyst",
                "company": "Zscaler",
                "url": "https://example.com/z",
            }
        )

        mock_job_repo.find_cross_source_duplicate.assert_awaited_once_with(
            "SOC Analyst",
            "Zscaler",
        )

    @pytest.mark.asyncio
    async def test_get_job(self, service, mock_job_repo):
        """Test getting a job by ID."""
        mock_job_repo.get_by_id.return_value = Job(
            id="test-id",
            title="Test Job",
            company="Test Company",
        )

        result = await service.get_job("test-id")

        assert result is not None
        assert result.id == "test-id"
        mock_job_repo.get_by_id.assert_called_once_with("test-id")

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, service, mock_job_repo):
        """Test getting a non-existent job returns None."""
        mock_job_repo.get_by_id.return_value = None

        result = await service.get_job("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_jobs(self, service, mock_job_repo):
        """Test getting list of jobs."""
        mock_job_repo.get_active_jobs.return_value = [
            Job(id="1", title="Job 1", company="Company 1"),
            Job(id="2", title="Job 2", company="Company 2"),
        ]
        mock_job_repo.count.return_value = 2

        result = await service.get_jobs(skip=0, limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_jobs(self, service, mock_job_repo):
        """Test job search."""
        mock_job_repo.search_jobs.return_value = [
            Job(id="1", title="Python Developer", company="TechCorp"),
        ]

        result = await service.search_jobs("python", limit=10)

        assert len(result) == 1
        mock_job_repo.search_jobs.assert_called_once_with("python", 10)

    @pytest.mark.asyncio
    async def test_save_jobs_filters_duplicates(self, service, mock_job_repo):
        """Test that save_jobs filters out duplicates."""
        # First job succeeds, second is duplicate
        mock_job_repo.get_by_url.side_effect = [None, Job(id="existing")]

        jobs_data = [
            {"title": "Job 1", "company": "C1", "url": "https://new.com"},
            {"title": "Job 2", "company": "C2", "url": "https://existing.com"},
        ]

        result = await service.save_jobs(jobs_data)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_job_statistics(self, service, mock_job_repo):
        """Test getting job statistics."""
        mock_job_repo.count.return_value = 100
        mock_job_repo.get_salary_statistics.return_value = {
            "min_salary": 50000,
            "max_salary": 150000,
            "avg_min": 75000,
            "avg_max": 125000,
        }
        mock_job_repo.get_top_companies.return_value = [
            ("TechCorp", 10),
            ("StartupXYZ", 5),
        ]
        mock_job_repo.get_job_type_distribution.return_value = [
            (JobType.FULL_TIME, 60),
            (JobType.REMOTE, 30),
        ]

        result = await service.get_job_statistics()

        assert "total_jobs" in result
        assert "salary_stats" in result
        assert "top_companies" in result
        assert "job_types" in result
