"""Tests for GET /applications/{id}/history (status-change timeline)."""

import pytest
from httpx import AsyncClient


class TestApplicationHistoryAPI:
    """Tests for the application status-history endpoint."""

    @pytest.mark.asyncio
    async def test_history_404_when_application_missing(self, client: AsyncClient):
        """Unknown application id -> 404 with a clear message."""
        response = await client.get("/api/v1/applications/does-not-exist/history")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_history_empty_when_no_changes(
        self,
        client: AsyncClient,
        db_session,
    ):
        """An application that never changed status has an empty timeline."""
        from interntrack.domain.models import Application, Job

        db_session.add(
            Job(
                id="hist-job-empty",
                title="Security Analyst",
                company="Zscaler",
                url="https://example.com/job/hist-empty",
            )
        )
        db_session.add(
            Application(id="hist-app-empty", job_id="hist-job-empty", status="saved")
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/hist-app-empty/history")
        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "hist-app-empty"
        assert data["history"] == []

    @pytest.mark.asyncio
    async def test_history_lists_changes_oldest_first(
        self,
        client: AsyncClient,
        db_session,
    ):
        """Status changes come back oldest-first with their timestamps."""
        from interntrack.domain.models import (
            Application,
            ApplicationStatusHistory,
            Job,
        )

        db_session.add(
            Job(
                id="hist-job-1",
                title="Pen Tester",
                company="Acme",
                url="https://example.com/job/hist-1",
            )
        )
        db_session.add(
            Application(id="hist-app-1", job_id="hist-job-1", status="interview")
        )
        await db_session.flush()
        db_session.add(
            ApplicationStatusHistory(
                application_id="hist-app-1",
                old_status="saved",
                new_status="applied",
            )
        )
        db_session.add(
            ApplicationStatusHistory(
                application_id="hist-app-1",
                old_status="applied",
                new_status="interview",
            )
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/hist-app-1/history")
        assert response.status_code == 200
        data = response.json()
        statuses = [item["status"] for item in data["history"]]
        # applied (saved -> applied) then interview (applied -> interview).
        assert statuses == ["applied", "interview"]
        assert all(item.get("changed_at") for item in data["history"])

    @pytest.mark.asyncio
    async def test_history_records_real_status_update(
        self,
        client: AsyncClient,
        db_session,
    ):
        """A status change made through the PATCH endpoint lands in history."""
        from interntrack.domain.models import Application, Job

        db_session.add(
            Job(
                id="hist-job-2",
                title="SOC Analyst",
                company="Cloudflare",
                url="https://example.com/job/hist-2",
            )
        )
        db_session.add(
            Application(id="hist-app-2", job_id="hist-job-2", status="saved")
        )
        await db_session.flush()

        response = await client.patch(
            "/api/v1/applications/hist-app-2/status",
            json={"status": "applied"},
        )
        assert response.status_code == 200

        history_resp = await client.get("/api/v1/applications/hist-app-2/history")
        assert history_resp.status_code == 200
        statuses = [item["status"] for item in history_resp.json()["history"]]
        assert statuses == ["applied"]
