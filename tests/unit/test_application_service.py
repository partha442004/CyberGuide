"""
Unit tests for ApplicationService.
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from interntrack.services.application_service import ApplicationService
from interntrack.domain.models import Application
from interntrack.domain.enums import ApplicationStatus


class TestApplicationService:
    """Tests for ApplicationService."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_app_repo(self):
        """Mock application repository."""
        repo = AsyncMock()
        repo.get_by_id.return_value = None
        repo.get_by_job_id.return_value = None
        repo.create.return_value = Application(
            id="test-app-123",
            job_id="test-job-123",
            status=ApplicationStatus.SAVED,
        )
        repo.get_by_status.return_value = []
        repo.get_status_counts.return_value = {
            "saved": 5,
            "applied": 10,
            "interview": 3,
            "rejected": 2,
            "offer": 1,
        }
        repo.get_recent_applications.return_value = []
        repo.get_rejection_rate.return_value = 13.33
        repo.get_response_rate.return_value = 23.08
        return repo

    @pytest.fixture
    def service(self, mock_session, mock_app_repo):
        """Create ApplicationService with mocked dependencies."""
        service = ApplicationService(mock_session)
        service.app_repo = mock_app_repo
        return service

    @pytest.mark.asyncio
    async def test_create_application(self, service, mock_app_repo):
        """Test creating a new application."""
        result = await service.create_application("job-123")

        assert result is not None
        assert result.job_id == "test-job-123"
        assert result.status == ApplicationStatus.SAVED
        mock_app_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_application(self, service, mock_app_repo):
        """Test getting an application by ID."""
        mock_app_repo.get_by_id.return_value = Application(
            id="app-123",
            job_id="job-123",
            status=ApplicationStatus.APPLIED,
        )

        result = await service.get_application("app-123")

        assert result is not None
        assert result.id == "app-123"

    @pytest.mark.asyncio
    async def test_get_application_for_job(self, service, mock_app_repo):
        """Test getting application for a specific job."""
        mock_app_repo.get_by_job_id.return_value = Application(
            id="app-456",
            job_id="job-123",
            status=ApplicationStatus.SAVED,
        )

        result = await service.get_application_for_job("job-123")

        assert result is not None
        assert result.job_id == "job-123"

    @pytest.mark.asyncio
    async def test_update_status(self, service, mock_app_repo):
        """Test updating application status."""
        mock_app_repo.update_status.return_value = Application(
            id="app-123",
            job_id="job-123",
            status=ApplicationStatus.APPLIED,
        )

        result = await service.update_status(
            "app-123",
            ApplicationStatus.APPLIED,
            notes="Applied via LinkedIn",
        )

        assert result is not None
        mock_app_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_applications_by_status(self, service, mock_app_repo):
        """Test getting applications by status."""
        mock_app_repo.get_by_status.return_value = [
            Application(id="1", job_id="job-1", status=ApplicationStatus.SAVED),
            Application(id="2", job_id="job-2", status=ApplicationStatus.SAVED),
        ]

        result = await service.get_applications_by_status(ApplicationStatus.SAVED)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_status_counts(self, service, mock_app_repo):
        """Test getting status counts."""
        result = await service.get_status_counts()

        assert "saved" in result
        assert "applied" in result
        assert result["saved"] == 5
        assert result["applied"] == 10

    @pytest.mark.asyncio
    async def test_get_metrics(self, service, mock_app_repo):
        """Test getting application metrics."""
        result = await service.get_metrics()

        assert "total_applications" in result
        assert "status_counts" in result
        assert "rejection_rate" in result
        assert "response_rate" in result

    @pytest.mark.asyncio
    async def test_get_pending_reminders(self, service, mock_app_repo):
        """Test getting applications needing reminders."""
        mock_app_repo.get_pending_reminders.return_value = [
            Application(id="1", job_id="job-1", reminded=False),
        ]

        result = await service.get_pending_reminders()

        assert len(result) == 1
