"""
Integration tests for API endpoints.
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health endpoint returns healthy status with DB probe."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "ok"
        assert data["version"]

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns app info."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestJobsAPI:
    """Tests for Jobs API endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs(self, client: AsyncClient):
        """Test listing jobs returns empty list initially."""
        response = await client.get("/api/v1/jobs/")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_job(self, client: AsyncClient, mock_job_data):
        """Test creating a new job."""
        response = await client.post("/api/v1/jobs/", json=mock_job_data)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == mock_job_data["title"]
        assert data["company"] == mock_job_data["company"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_job(self, client: AsyncClient, mock_job_data):
        """Test getting a specific job."""
        # Create job first
        create_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = create_response.json()["id"]

        # Get job
        response = await client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: AsyncClient):
        """Test getting non-existent job returns 404."""
        response = await client.get("/api/v1/jobs/non-existent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_job(self, client: AsyncClient, mock_job_data):
        """Test updating a job."""
        # Create job first
        create_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = create_response.json()["id"]

        # Update job
        update_data = {"title": "Updated Python Developer"}
        response = await client.put(f"/api/v1/jobs/{job_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Python Developer"

    @pytest.mark.asyncio
    async def test_delete_job(self, client: AsyncClient, mock_job_data):
        """Test deleting a job."""
        # Create job first
        create_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = create_response.json()["id"]

        # Delete job
        response = await client.delete(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 204

        # Verify deletion
        get_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_search_jobs(self, client: AsyncClient, mock_job_data):
        """Test searching jobs."""
        # Create job first
        await client.post("/api/v1/jobs/", json=mock_job_data)

        # Search
        search_data = {"query": "Python", "limit": 10}
        response = await client.post("/api/v1/jobs/search", json=search_data)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_job_statistics(self, client: AsyncClient):
        """Test getting job statistics."""
        response = await client.get("/api/v1/jobs/stats/overview")

        assert response.status_code == 200
        data = response.json()
        assert "total_jobs" in data
        assert "salary_stats" in data


class TestApplicationsAPI:
    """Tests for Applications API endpoints."""

    @pytest.mark.asyncio
    async def test_list_applications(self, client: AsyncClient):
        """Test listing applications."""
        response = await client.get("/api/v1/applications/")

        assert response.status_code == 200
        data = response.json()
        assert "applications" in data

    @pytest.mark.asyncio
    async def test_create_application(self, client: AsyncClient, mock_job_data):
        """Test creating an application."""
        # Create job first
        job_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = job_response.json()["id"]

        # Create application
        app_data = {"job_id": job_id}
        response = await client.post("/api/v1/applications/", json=app_data)

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "saved"

    @pytest.mark.asyncio
    async def test_update_application_status(self, client: AsyncClient, mock_job_data):
        """Test updating application status."""
        # Create job and application
        job_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = job_response.json()["id"]

        app_response = await client.post(
            "/api/v1/applications/",
            json={"job_id": job_id},
        )
        app_id = app_response.json()["id"]

        # Update status
        status_update = {"status": "applied", "notes": "Applied via website"}
        response = await client.patch(
            f"/api/v1/applications/{app_id}/status",
            json=status_update,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "applied"

    @pytest.mark.asyncio
    async def test_application_metrics(self, client: AsyncClient):
        """Test getting application metrics."""
        response = await client.get("/api/v1/applications/metrics/overview")

        assert response.status_code == 200
        data = response.json()
        assert "total_applications" in data
        assert "status_counts" in data


class TestReportsAPI:
    """Tests for Reports API endpoints."""

    @pytest.mark.asyncio
    async def test_daily_report(self, client: AsyncClient):
        """Test generating daily report."""
        response = await client.get("/api/v1/reports/daily")

        assert response.status_code == 200
        data = response.json()
        assert data["report_type"] == "daily"
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_weekly_report(self, client: AsyncClient):
        """Test generating weekly report."""
        response = await client.get("/api/v1/reports/weekly")

        assert response.status_code == 200
        data = response.json()
        assert data["report_type"] == "weekly"

    @pytest.mark.asyncio
    async def test_monthly_report(self, client: AsyncClient):
        """Test generating monthly report."""
        response = await client.get("/api/v1/reports/monthly")

        assert response.status_code == 200
        data = response.json()
        assert data["report_type"] == "monthly"


class TestNotificationsAPI:
    """Tests for Notifications API endpoints."""

    @pytest.mark.asyncio
    async def test_get_channels(self, client: AsyncClient):
        """Test getting configured notification channels."""
        response = await client.get("/api/v1/notifications/channels")

        assert response.status_code == 200
        data = response.json()
        assert "channels" in data


class TestCorsMiddleware:
    """Tests for CORS middleware wiring."""

    @pytest.mark.asyncio
    async def test_cors_preflight(self, client: AsyncClient):
        """OPTIONS preflight from an allowed origin returns CORS headers."""
        response = await client.options(
            "/api/v1/jobs/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"

    @pytest.mark.asyncio
    async def test_cors_headers_on_regular_request(self, client: AsyncClient):
        """Regular requests from an allowed origin include CORS headers."""
        response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"


class TestDashboardAPI:
    """Tests for Dashboard API endpoints."""

    @pytest.mark.asyncio
    async def test_dashboard_overview(self, client: AsyncClient):
        """Test getting dashboard overview."""
        response = await client.get("/api/v1/dashboard/overview")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "applications" in data

    @pytest.mark.asyncio
    async def test_job_type_chart(self, client: AsyncClient):
        """Test getting job type chart data."""
        response = await client.get("/api/v1/dashboard/charts/job-types")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_application_timeline(self, client: AsyncClient):
        """Test getting application timeline."""
        response = await client.get("/api/v1/dashboard/charts/application-timeline")

        assert response.status_code == 200
