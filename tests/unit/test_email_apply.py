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


class TestClosingSoonHtml:
    """Closing-soon emails reuse the styled card with tracked Apply links."""

    def test_tracking_links_when_api_base_known(self):
        from interntrack.scheduler.jobs import _closing_soon_html
        from interntrack.utils.helpers import verify_apply_token

        html = _closing_soon_html(
            [
                {
                    "id": "cj-1",
                    "title": "SOC Analyst",
                    "company": "Acme",
                    "location": "Bangalore",
                    "url": "https://jobs.acme.com/1",
                    "expires_at": "2026-08-20T12:00:00",
                }
            ],
            "u-cj",
            "https://api.example.com",
        )
        assert "Closing soon" in html
        assert "SOC Analyst" in html
        assert "api/v1/email/apply?u=u-cj&amp;j=cj-1&amp;t=" in html
        token = html.split("&amp;t=")[-1].split("'")[0]
        assert verify_apply_token("u-cj", "cj-1", token)

    def test_plain_url_without_api_base(self):
        from interntrack.scheduler.jobs import _closing_soon_html

        html = _closing_soon_html(
            [
                {
                    "id": "cj-2",
                    "title": "VAPT",
                    "company": "Acme",
                    "location": "Remote",
                    "url": "https://jobs.acme.com/2",
                    "expires_at": None,
                }
            ],
            None,
            "",
        )
        assert "href='https://jobs.acme.com/2'" in html
        assert "api/v1/email/apply" not in html


class TestEmailStatusEndpoint:
    """GET /api/v1/email/status — one-click nudge status buttons."""

    @pytest.mark.asyncio
    async def test_updates_application_and_confirms(self, client, db_session):
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import select

        from interntrack.domain.enums import ApplicationStatus
        from interntrack.domain.models import Application, Job
        from interntrack.utils.helpers import status_token

        db_session.add(
            Job(
                id="job-st-1",
                title="SOC Analyst",
                company="Acme",
                url="https://x.com/1",
            )
        )
        db_session.add(
            Application(
                id="app-st-1",
                job_id="job-st-1",
                user_id="u-st-1",
                status=ApplicationStatus.APPLIED,
                applied_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=9),
            )
        )
        await db_session.flush()

        token = status_token("u-st-1", "app-st-1", "interview")
        resp = await client.get(
            "/api/v1/email/status",
            params={"u": "u-st-1", "a": "app-st-1", "s": "interview", "t": token},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "Status updated" in resp.text

        result = await db_session.execute(
            select(Application).where(Application.id == "app-st-1")
        )
        app = result.scalars().first()
        assert app is not None
        assert app.status == ApplicationStatus.INTERVIEW

    @pytest.mark.asyncio
    async def test_other_users_application_rejected(self, client, db_session):
        from datetime import UTC, datetime, timedelta

        from interntrack.domain.enums import ApplicationStatus
        from interntrack.domain.models import Application, Job
        from interntrack.utils.helpers import status_token

        db_session.add(
            Job(id="job-st-2", title="Analyst", company="Acme", url="https://x.com/2")
        )
        db_session.add(
            Application(
                id="app-st-2",
                job_id="job-st-2",
                user_id="u-other",
                status=ApplicationStatus.APPLIED,
                applied_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=9),
            )
        )
        await db_session.flush()

        token = status_token("u-st-2", "app-st-2", "offer")
        resp = await client.get(
            "/api/v1/email/status",
            params={"u": "u-st-2", "a": "app-st-2", "s": "offer", "t": token},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_token_and_status_rejected(self, client):
        bad_token = await client.get(
            "/api/v1/email/status",
            params={"u": "u", "a": "a", "s": "interview", "t": "f" * 64},
        )
        assert bad_token.status_code == 400
        bad_status = await client.get(
            "/api/v1/email/status",
            params={"u": "u", "a": "a", "s": "hacked", "t": "f" * 64},
        )
        assert bad_status.status_code == 400
