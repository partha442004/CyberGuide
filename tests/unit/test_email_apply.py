"""
Tests for the email apply-tracking links (signed "Apply now" buttons).

Members who never open the dashboard still record applications by clicking
the Apply button in their digest email — the button points at a signed
``/api/v1/email/apply`` link that records the application, then opens the
job. These tests cover the token, the card rendering, and the endpoint.
"""

import pytest

from interntrack.domain.models import Job
from interntrack.scheduler.jobs import _apply_link, _job_html_card
from interntrack.utils.helpers import apply_token, verify_apply_token


class TestApplyToken:
    """HMAC token helpers."""

    def test_roundtrip(self):
        token = apply_token("user-1", "job-1")
        assert verify_apply_token("user-1", "job-1", token) is True

    def test_tampered_token_rejected(self):
        token = apply_token("user-1", "job-1")
        assert verify_apply_token("user-1", "job-1", token + "x") is False
        assert verify_apply_token("user-2", "job-1", token) is False
        assert verify_apply_token("user-1", "job-2", token) is False

    def test_missing_token_rejected(self):
        assert verify_apply_token("u", "j", "") is False

    def test_open_and_apply_tokens_are_scoped(self):
        from interntrack.utils.helpers import open_token, verify_open_token

        apply_tok = apply_token("user-1", "job-1")
        open_tok = open_token("user-1")
        assert verify_open_token("user-1", apply_tok) is False
        assert verify_open_token("user-1", open_tok) is True
        assert verify_apply_token("user-1", "job-1", open_tok) is False


class TestApplyLinkHelper:
    """The digest-side link builder."""

    def test_builds_signed_url(self):
        link = _apply_link("https://api.example.com", "user-1", "job-1")
        assert link is not None
        assert link.startswith(
            "https://api.example.com/api/v1/email/apply?u=user-1&j=job-1&t="
        )
        token = link.split("t=")[-1]
        assert verify_apply_token("user-1", "job-1", token)

    def test_requires_all_parts(self):
        assert _apply_link("", "user-1", "job-1") is None
        assert _apply_link("https://api.example.com", None, "job-1") is None
        assert _apply_link("https://api.example.com", "user-1", None) is None


class TestJobCardTrackingLink:
    """The HTML card Apply button."""

    def test_card_uses_tracking_link_when_given(self):
        card = _job_html_card(
            80,
            {
                "id": "j1",
                "title": "SOC Analyst",
                "company": "Acme",
                "location": "Bangalore",
                "url": "https://jobs.acme.com/1",
            },
            "#0ea5e9",
            apply_link="https://api.example.com/api/v1/email/apply?u=u&j=j1&t=tok",
        )
        assert (
            "https://api.example.com/api/v1/email/apply?u=u&amp;j=j1&amp;t=tok" in card
        )
        assert "href='https://jobs.acme.com/1'" not in card

    def test_card_keeps_direct_url_without_tracking(self):
        card = _job_html_card(
            80,
            {
                "id": "j1",
                "title": "SOC Analyst",
                "company": "Acme",
                "location": "Bangalore",
                "url": "https://jobs.acme.com/1",
            },
            "#0ea5e9",
        )
        assert "href='https://jobs.acme.com/1'" in card


class TestEmailApplyEndpoint:
    """GET /api/v1/email/apply — records the application, then redirects."""

    @pytest.mark.asyncio
    async def test_valid_link_records_application_and_redirects(
        self, client, db_session
    ):
        db_session.add(
            Job(
                id="job-apply-1",
                title="SOC Analyst",
                company="Acme",
                location="Bangalore",
                url="https://jobs.acme.com/1",
            )
        )
        await db_session.flush()

        token = apply_token("user-apply-1", "job-apply-1")
        resp = await client.get(
            "/api/v1/email/apply",
            params={"u": "user-apply-1", "j": "job-apply-1", "t": token},
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://jobs.acme.com/1"

        listing = await client.get("/api/v1/applications/")
        assert listing.status_code == 200
        mine = [
            a for a in listing.json()["applications"] if a["user_id"] == "user-apply-1"
        ]
        assert len(mine) == 1
        assert mine[0]["job_id"] == "job-apply-1"
        assert mine[0]["status"] == "applied"

        # The row is tagged source="email" so the owner recap can count
        # member activity recorded straight from digest emails.
        from sqlalchemy import select

        from interntrack.domain.models import Application

        result = await db_session.execute(
            select(Application).where(Application.user_id == "user-apply-1")
        )
        app = result.scalars().first()
        assert app is not None
        assert app.source == "email"

    @pytest.mark.asyncio
    async def test_second_click_is_idempotent(self, client, db_session):
        db_session.add(
            Job(
                id="job-apply-2",
                title="Security Engineer",
                company="Acme",
                location="Remote",
                url="https://jobs.acme.com/2",
            )
        )
        await db_session.flush()

        params = {
            "u": "user-apply-2",
            "j": "job-apply-2",
            "t": apply_token("user-apply-2", "job-apply-2"),
        }
        await client.get("/api/v1/email/apply", params=params)
        await client.get("/api/v1/email/apply", params=params)

        listing = await client.get("/api/v1/applications/")
        mine = [
            a for a in listing.json()["applications"] if a["user_id"] == "user-apply-2"
        ]
        assert len(mine) == 1

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self, client, db_session):
        db_session.add(
            Job(
                id="job-apply-3",
                title="SOC Analyst",
                company="Acme",
                location="Bangalore",
                url="https://jobs.acme.com/3",
            )
        )
        await db_session.flush()

        resp = await client.get(
            "/api/v1/email/apply",
            params={"u": "user-apply-3", "j": "job-apply-3", "t": "f" * 64},
        )
        assert resp.status_code == 400

        listing = await client.get("/api/v1/applications/")
        mine = [
            a for a in listing.json()["applications"] if a["user_id"] == "user-apply-3"
        ]
        assert mine == []


class TestEmailOpenPixel:
    """GET /api/v1/email/open — stamps opened_at, answers a 1x1 GIF."""

    @pytest.mark.asyncio
    async def test_open_marks_latest_digest(self, client, db_session):
        from sqlalchemy import select

        from interntrack.domain.models import NotificationHistory
        from interntrack.utils.helpers import open_token

        db_session.add(
            NotificationHistory(user_id="u-open-1", subject="Daily", job_count=2)
        )
        await db_session.flush()

        resp = await client.get(
            "/api/v1/email/open",
            params={"u": "u-open-1", "t": open_token("u-open-1")},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/gif"

        result = await db_session.execute(
            select(NotificationHistory).where(NotificationHistory.user_id == "u-open-1")
        )
        row = result.scalars().first()
        assert row is not None
        assert row.opened_at is not None

    @pytest.mark.asyncio
    async def test_invalid_open_token_rejected(self, client):
        resp = await client.get(
            "/api/v1/email/open",
            params={"u": "u-open-2", "t": "f" * 64},
        )
        assert resp.status_code == 400
