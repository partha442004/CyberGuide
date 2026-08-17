"""
Tests for the bounded dead-link sweep endpoint (POST /api/v1/jobs/verify-links).

The endpoint checks the least-recently-verified active job links, skips
hosts known to block server IPs, and deactivates only jobs whose pages are
definitively gone (404/410).
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_verify_links_marks_dead_and_skips_blocked(client):
    """A 404 on a checkable host deactivates the job; bot-blocked hosts are skipped."""
    from interntrack.api.v1.jobs import _host_is_bot_blocked

    assert _host_is_bot_blocked("https://in.indeed.com/viewjob?jk=abc") is True
    assert _host_is_bot_blocked("https://jobdexo.com/job/x") is False

    # Seed a job on a checkable host.
    created = await client.post(
        "/api/v1/jobs/share",
        json={
            "url": "https://jobdexo.example/job/gone-1",
            "title": "SOC Analyst",
            "company": "Acme",
        },
    )
    assert created.status_code == 200, created.text

    # A HEAD to jobdexo.example returns 404 -> dead.
    async def fake_head(*args, **kwargs):
        resp = AsyncMock()
        resp.status_code = 404
        return resp

    with patch(
        "httpx.AsyncClient.__aenter__",
        new=AsyncMock(return_value=AsyncMock(head=fake_head)),
    ):
        resp = await client.post("/api/v1/jobs/verify-links?limit=25")
        assert resp.status_code == 200, resp.text
        data = resp.json()

    assert data["dead"] >= 1, data
    assert any(r["status"] == "dead" for r in data["results"]), data

    # The dead job is no longer listable as active.
    listing = await client.get("/api/v1/jobs/?limit=100")
    titles = [j["title"] for j in listing.json()["jobs"]]
    assert "SOC Analyst" not in titles


@pytest.mark.asyncio
async def test_verify_links_keeps_alive_jobs(client):
    """A 200 on a checkable host keeps the job active and marks it verified."""
    created = await client.post(
        "/api/v1/jobs/share",
        json={
            "url": "https://alive.example/job/keep-1",
            "title": "Threat Analyst",
            "company": "Acme",
        },
    )
    assert created.status_code == 200, created.text

    async def fake_head(*args, **kwargs):
        resp = AsyncMock()
        resp.status_code = 200
        return resp

    with patch(
        "httpx.AsyncClient.__aenter__",
        new=AsyncMock(return_value=AsyncMock(head=fake_head)),
    ):
        resp = await client.post("/api/v1/jobs/verify-links?limit=25")
        assert resp.status_code == 200, resp.text
        data = resp.json()

    assert data["checked"] >= 1, data
    assert data["dead"] == 0, data
    assert any(r["status"] == "alive" for r in data["results"]), data

    listing = await client.get("/api/v1/jobs/?limit=100")
    titles = [j["title"] for j in listing.json()["jobs"]]
    assert "Threat Analyst" in titles
