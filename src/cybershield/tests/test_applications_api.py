"""
Tests for the Applications API Router.

Integration tests exercising list/get/create/status-update/history/metrics
and deadline endpoints against the test database.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from cybershield.domain.models import Application, Job

APP_URL = "/api/v1/applications/"


async def _create_job(db_session, title="Security Analyst", **overrides) -> Job:
    """Create a minimal job row."""
    job = Job(
        title=title,
        company=overrides.pop("company", "Acme Corp"),
        url=overrides.pop("url", f"https://acme.com/job/{abs(hash(title)) % 100000}"),
        source="test",
        job_type="full_time",
        **overrides,
    )
    db_session.add(job)
    await db_session.flush()
    return job


async def _create_application(db_session, user_id, job, status="saved", **overrides) -> Application:
    """Create a minimal application row."""
    app = Application(
        user_id=user_id,
        job_id=job.id,
        status=status,
        **overrides,
    )
    db_session.add(app)
    await db_session.flush()
    return app


class TestListApplications:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        response = await client.get(APP_URL, params={"user_id": "no-apps-user"})
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_with_applications(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Analyst One")
        await _create_application(db_session, "list-user", job)

        response = await client.get(APP_URL, params={"user_id": "list-user"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_list_filtered_by_status(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Analyst Two")
        await _create_application(db_session, "filter-user", job, status="applied")
        await _create_application(db_session, "filter-user", job, status="saved")

        response = await client.get(APP_URL, params={"user_id": "filter-user", "status": "applied"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "applied"

    @pytest.mark.asyncio
    async def test_list_respects_skip_and_limit(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Analyst Three")
        for _ in range(5):
            await _create_application(db_session, "page-user", job)

        response = await client.get(APP_URL, params={"user_id": "page-user", "skip": 0, "limit": 2})
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGetApplication:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Get Me")
        app = await _create_application(db_session, "get-user", job)

        response = await client.get(f"{APP_URL}{app.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == app.id
        assert data["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_get_missing_returns_404(self, client: AsyncClient):
        response = await client.get(f"{APP_URL}no-such-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Application not found"


class TestCreateApplication:
    @pytest.mark.asyncio
    async def test_create(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Create Target")

        response = await client.post(
            APP_URL,
            json={"user_id": "create-user", "job_id": job.id, "status": "saved"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "create-user"
        assert data["job_id"] == job.id
        assert data["status"] == "saved"


class TestUpdateApplicationStatus:
    @pytest.mark.asyncio
    async def test_update_valid_status(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Status Target")
        app = await _create_application(db_session, "status-user", job)

        response = await client.patch(
            f"{APP_URL}{app.id}/status",
            json={"status": "applied", "notes": "submitted resume"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "applied"
        assert "submitted resume" in data["notes"]

    @pytest.mark.asyncio
    async def test_update_invalid_status_returns_422(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Bad Status")
        app = await _create_application(db_session, "status-user2", job)

        response = await client.patch(
            f"{APP_URL}{app.id}/status",
            json={"status": "not-a-real-status"},
        )
        assert response.status_code == 422


class TestGetApplicationHistory:
    @pytest.mark.asyncio
    async def test_history_empty_for_new_app(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "History Job")
        app = await _create_application(db_session, "history-user", job)

        response = await client.get(f"{APP_URL}{app.id}/history")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_history_after_status_change(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "History Job 2")
        app = await _create_application(db_session, "history-user2", job)

        await client.patch(f"{APP_URL}{app.id}/status", json={"status": "applied"})

        response = await client.get(f"{APP_URL}{app.id}/history")
        assert response.status_code == 200
        history = response.json()
        assert len(history) >= 1
        assert history[0]["new_status"] == "applied"


class TestGetUserMetrics:
    @pytest.mark.asyncio
    async def test_metrics_empty(self, client: AsyncClient):
        response = await client.get(f"{APP_URL}user/metrics-user/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_metrics_with_data(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Metrics Job")
        await _create_application(db_session, "metrics-user", job, status="saved")
        await _create_application(db_session, "metrics-user", job, status="interview")

        response = await client.get(f"{APP_URL}user/metrics-user/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["by_status"]["saved"] == 1
        assert data["by_status"]["interview"] == 1
        assert data["success_rate"] == 50.0


class TestGetUpcomingDeadlines:
    @pytest.mark.asyncio
    async def test_deadlines_empty(self, client: AsyncClient):
        response = await client.get(f"{APP_URL}user/deadline-user/deadlines")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_deadlines_with_upcoming_interview(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Deadline Job")
        future = datetime.now(timezone.utc) + timedelta(days=2)
        await _create_application(
            db_session,
            "deadline-user",
            job,
            status="interview",
            interview_at=future,
        )

        response = await client.get(f"{APP_URL}user/deadline-user/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "interview"
