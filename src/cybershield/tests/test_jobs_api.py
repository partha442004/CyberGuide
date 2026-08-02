"""
Tests for the Jobs API Router.

Integration tests exercising list/search/get/create/update/delete and
expiring-soon endpoints against the test database.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from cybershield.domain.models import Job

JOB_URL = "/api/v1/jobs/"


async def _create_job(db_session, title="Security Analyst", **overrides) -> Job:
    """Create a minimal job row."""
    job = Job(
        title=title,
        company=overrides.pop("company", "Acme Corp"),
        url=overrides.pop("url", f"https://acme.com/job/{abs(hash(title)) % 100000}"),
        source="test",
        job_type=overrides.pop("job_type", "full_time"),
        **overrides,
    )
    db_session.add(job)
    await db_session.flush()
    return job


class TestListJobs:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        response = await client.get(JOB_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_jobs(self, client: AsyncClient, db_session):
        await _create_job(db_session, "Job A")
        await _create_job(db_session, "Job B", company="Beta Corp")

        response = await client.get(JOB_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_country_and_type(self, client: AsyncClient, db_session):
        await _create_job(db_session, "USA Job", country="USA", job_type="full_time")
        await _create_job(db_session, "India Job", country="India", job_type="internship")

        response = await client.get(JOB_URL, params={"country": "USA", "job_type": "full_time"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "USA Job"

    @pytest.mark.asyncio
    async def test_list_respects_pagination(self, client: AsyncClient, db_session):
        for i in range(5):
            await _create_job(db_session, f"Page Job {i}")

        response = await client.get(JOB_URL, params={"skip": 0, "limit": 2})
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2


class TestSearchJobs:
    @pytest.mark.asyncio
    async def test_search_by_query(self, client: AsyncClient, db_session):
        await _create_job(db_session, "Python Developer")
        await _create_job(db_session, "Go Developer")

        response = await client.get(f"{JOB_URL}search", params={"q": "python"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all("python" in item["title"].lower() for item in data["items"])

    @pytest.mark.asyncio
    async def test_search_requires_query(self, client: AsyncClient):
        response = await client.get(f"{JOB_URL}search")
        assert response.status_code == 422


class TestGetJob:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Get This Job")

        response = await client.get(f"{JOB_URL}{job.id}")
        assert response.status_code == 200
        assert response.json()["id"] == job.id

    @pytest.mark.asyncio
    async def test_get_missing_returns_404(self, client: AsyncClient):
        response = await client.get(f"{JOB_URL}no-such-job")
        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"


class TestCreateJob:
    @pytest.mark.asyncio
    async def test_create(self, client: AsyncClient):
        response = await client.post(
            JOB_URL,
            json={
                "title": "Newly Created Job",
                "company": "Fresh Corp",
                "url": "https://fresh.com/job/1",
                "source": "manual",
                "job_type": "full_time",
                "country": "USA",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Newly Created Job"
        assert data["company"] == "Fresh Corp"


class TestUpdateJob:
    @pytest.mark.asyncio
    async def test_update_existing(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Before Update")

        response = await client.put(
            f"{JOB_URL}{job.id}",
            json={"title": "After Update", "description": "updated desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "After Update"
        assert data["description"] == "updated desc"


class TestDeleteJob:
    @pytest.mark.asyncio
    async def test_delete_existing(self, client: AsyncClient, db_session):
        job = await _create_job(db_session, "Delete Me")

        response = await client.delete(f"{JOB_URL}{job.id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"{JOB_URL}{job.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_missing_returns_404(self, client: AsyncClient):
        response = await client.delete(f"{JOB_URL}no-such-job")
        assert response.status_code == 404


class TestExpiringSoon:
    @pytest.mark.asyncio
    async def test_expiring_empty(self, client: AsyncClient):
        response = await client.get(f"{JOB_URL}expiring-soon")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_expiring_with_deadline(self, client: AsyncClient, db_session):
        soon = datetime.now(timezone.utc) + timedelta(days=2)
        await _create_job(db_session, "Expiring Job", expires_at=soon)
        far = datetime.now(timezone.utc) + timedelta(days=90)
        await _create_job(db_session, "Far Job", expires_at=far)

        response = await client.get(f"{JOB_URL}expiring-soon", params={"days": 7})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Expiring Job"
