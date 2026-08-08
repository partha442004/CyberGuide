"""Tests for the ⭐ high-priority applications endpoint."""

import pytest
from httpx import AsyncClient


def _add_job(db_session, job_id: str, url: str) -> None:
    """Seed a minimal Job row (title/company/url are NOT NULL)."""
    from interntrack.domain.models import Job

    db_session.add(Job(id=job_id, title="Security Analyst", company="Zscaler", url=url))


class TestPriorityApplicationsAPI:
    """Tests for GET /applications/priority."""

    @pytest.mark.asyncio
    async def test_priority_empty_when_none_pinned(
        self, client: AsyncClient, db_session
    ):
        """No high-priority applications -> empty list."""
        from interntrack.domain.models import Application

        _add_job(db_session, "prio-job-0", "https://example.com/job/prio-0")
        db_session.add(
            Application(
                id="prio-app-0",
                job_id="prio-job-0",
                user_id="prio-user",
                status="applied",
            )  # priority defaults to 0
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/priority?user_id=prio-user")
        assert response.status_code == 200
        assert response.json()["applications"] == []

    @pytest.mark.asyncio
    async def test_priority_returns_pinned_most_important_first(
        self,
        client: AsyncClient,
        db_session,
    ):
        """priority>=1 comes back, sorted by priority desc."""
        from interntrack.domain.models import Application

        _add_job(db_session, "prio-job-1", "https://example.com/job/prio-1")
        db_session.add(
            Application(
                id="prio-app-1",
                job_id="prio-job-1",
                user_id="prio-user1",
                status="interview",
                priority=1,
            )
        )
        db_session.add(
            Application(
                id="prio-app-2",
                job_id="prio-job-1",
                user_id="prio-user1",
                status="applied",
                priority=3,
            )
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/priority?user_id=prio-user1")
        assert response.status_code == 200
        apps = response.json()["applications"]
        assert [a["id"] for a in apps] == ["prio-app-2", "prio-app-1"]
        assert apps[0]["priority"] == 3

    @pytest.mark.asyncio
    async def test_priority_scoped_by_user(self, client: AsyncClient, db_session):
        """Another user's pinned application never leaks in."""
        from interntrack.domain.models import Application

        _add_job(db_session, "prio-job-3", "https://example.com/job/prio-3")
        db_session.add(
            Application(
                id="prio-app-other",
                job_id="prio-job-3",
                user_id="someone-else",
                status="applied",
                priority=1,
            )
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/priority?user_id=prio-scoped")
        assert response.status_code == 200
        assert response.json()["applications"] == []


class TestPriorityToggle:
    """Tests for setting priority via PUT /applications/{id}."""

    @pytest.mark.asyncio
    async def test_set_and_clear_priority(self, client: AsyncClient, db_session):
        """PUT priority=1 pins it; PUT priority=0 unpins it."""
        from interntrack.domain.models import Application

        _add_job(db_session, "prio-job-4", "https://example.com/job/prio-4")
        db_session.add(
            Application(
                id="prio-app-4",
                job_id="prio-job-4",
                user_id="prio-user4",
                status="applied",
            )
        )
        await db_session.flush()

        # Pin it.
        pin = await client.put(
            "/api/v1/applications/prio-app-4",
            json={"priority": 1},
        )
        assert pin.status_code == 200
        assert pin.json()["priority"] == 1

        pinned = await client.get("/api/v1/applications/priority?user_id=prio-user4")
        assert [a["id"] for a in pinned.json()["applications"]] == ["prio-app-4"]

        # Unpin it.
        unpin = await client.put(
            "/api/v1/applications/prio-app-4",
            json={"priority": 0},
        )
        assert unpin.status_code == 200

        cleared = await client.get("/api/v1/applications/priority?user_id=prio-user4")
        assert cleared.json()["applications"] == []
