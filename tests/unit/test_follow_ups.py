"""Tests for application follow-up endpoints.

Covers ``GET /applications/follow-ups`` (pending-reminder applications,
most urgent first) and ``POST /applications/{id}/reminded`` (mark as
followed up).
"""

import pytest
from httpx import AsyncClient


def _add_job(
    db_session, job_id: str, url: str, title: str = "Security Analyst"
) -> None:
    """Seed a minimal Job row (title/company/url are NOT NULL)."""
    from interntrack.domain.models import Job

    db_session.add(Job(id=job_id, title=title, company="Zscaler", url=url))


class TestFollowUpsAPI:
    """Tests for the follow-ups endpoints."""

    @pytest.mark.asyncio
    async def test_follow_ups_empty_when_nothing_pending(
        self,
        client: AsyncClient,
        db_session,
    ):
        """No applications -> empty follow-ups list."""
        response = await client.get("/api/v1/applications/follow-ups?user_id=fu-empty")
        assert response.status_code == 200
        assert response.json()["follow_ups"] == []

    @pytest.mark.asyncio
    async def test_follow_ups_lists_pending_most_urgent_first(
        self,
        client: AsyncClient,
        db_session,
    ):
        """Applied/interview, un-reminded apps come back, newest-action last."""
        from datetime import timedelta

        from interntrack.domain.models import Application
        from interntrack.utils.helpers import utcnow

        _add_job(db_session, "fu-job-old", "https://example.com/job/fu-old")
        _add_job(db_session, "fu-job-new", "https://example.com/job/fu-new")
        db_session.add(
            Application(
                id="fu-app-old",
                job_id="fu-job-old",
                user_id="fu-user",
                status="applied",
                applied_at=utcnow() - timedelta(days=12),
            )
        )
        db_session.add(
            Application(
                id="fu-app-new",
                job_id="fu-job-new",
                user_id="fu-user",
                status="interview",
                applied_at=utcnow() - timedelta(days=3),
            )
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/follow-ups?user_id=fu-user")
        assert response.status_code == 200
        follow_ups = response.json()["follow_ups"]
        assert [item["application_id"] for item in follow_ups] == [
            "fu-app-old",
            "fu-app-new",
        ]
        assert follow_ups[0]["days_since"] == 12
        assert follow_ups[0]["job_title"] == "Security Analyst"
        assert follow_ups[0]["company"] == "Zscaler"
        assert follow_ups[0]["job_url"].endswith("/job/fu-old")

    @pytest.mark.asyncio
    async def test_follow_ups_excludes_reminded_and_other_statuses(
        self,
        client: AsyncClient,
        db_session,
    ):
        """Reminded, saved, and offer applications are not nudged."""
        from interntrack.domain.models import Application

        _add_job(db_session, "fu-job-2", "https://example.com/job/fu-2")
        # reminded -> excluded
        db_session.add(
            Application(
                id="fu-app-reminded",
                job_id="fu-job-2",
                user_id="fu-user2",
                status="applied",
                reminded=True,
            )
        )
        # saved -> excluded (only applied/interview are nudged)
        db_session.add(
            Application(
                id="fu-app-saved",
                job_id="fu-job-2",
                user_id="fu-user2",
                status="saved",
            )
        )
        # offer -> excluded
        db_session.add(
            Application(
                id="fu-app-offer",
                job_id="fu-job-2",
                user_id="fu-user2",
                status="offer",
            )
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/follow-ups?user_id=fu-user2")
        assert response.status_code == 200
        assert response.json()["follow_ups"] == []

    @pytest.mark.asyncio
    async def test_follow_ups_scoped_by_user(self, client: AsyncClient, db_session):
        """Another user's pending applications never leak in."""
        from interntrack.domain.models import Application

        _add_job(db_session, "fu-job-3", "https://example.com/job/fu-3")
        db_session.add(
            Application(
                id="fu-app-other",
                job_id="fu-job-3",
                user_id="someone-else",
                status="applied",
            )
        )
        await db_session.flush()

        response = await client.get("/api/v1/applications/follow-ups?user_id=fu-scoped")
        assert response.status_code == 200
        assert response.json()["follow_ups"] == []


class TestMarkRemindedAPI:
    """Tests for POST /applications/{id}/reminded."""

    @pytest.mark.asyncio
    async def test_mark_reminded_404_for_missing(self, client: AsyncClient):
        response = await client.post("/api/v1/applications/does-not-exist/reminded")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_reminded_removes_from_follow_ups(
        self,
        client: AsyncClient,
        db_session,
    ):
        """Marking an app followed-up drops it from the follow-ups list."""
        from interntrack.domain.models import Application

        _add_job(db_session, "fu-job-4", "https://example.com/job/fu-4")
        db_session.add(
            Application(
                id="fu-app-4",
                job_id="fu-job-4",
                user_id="fu-user4",
                status="applied",
            )
        )
        await db_session.flush()

        before = await client.get("/api/v1/applications/follow-ups?user_id=fu-user4")
        assert [i["application_id"] for i in before.json()["follow_ups"]] == [
            "fu-app-4"
        ]

        response = await client.post("/api/v1/applications/fu-app-4/reminded")
        assert response.status_code == 200

        after = await client.get("/api/v1/applications/follow-ups?user_id=fu-user4")
        assert after.json()["follow_ups"] == []
