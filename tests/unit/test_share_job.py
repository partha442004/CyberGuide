"""
Tests for the "Share a Job" endpoint — save any job link the user found,
with auto-detection of title/company from the page's OpenGraph meta tags.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestShareJob:
    """Share-a-job endpoint tests."""

    @pytest.mark.asyncio
    async def test_share_job_creates_job_with_full_details(self, client):
        resp = await client.post(
            "/api/v1/jobs/share",
            json={
                "url": "https://example.com/careers/soc-analyst",
                "title": "SOC Analyst",
                "company": "Acme Security",
                "location": "Remote",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["duplicate"] is False
        assert data["job"]["title"] == "SOC Analyst"
        assert data["job"]["company"] == "Acme Security"
        assert data["job"]["source"] == "manual"

        # The job is now listable.
        listing = await client.get("/api/v1/jobs/?limit=100")
        titles = [j["title"] for j in listing.json()["jobs"]]
        assert "SOC Analyst" in titles

    @pytest.mark.asyncio
    async def test_share_job_duplicate_url_is_idempotent(self, client):
        payload = {
            "url": "https://example.com/jobs/123",
            "title": "Penetration Tester",
            "company": "CyberCorp",
        }
        first = await client.post("/api/v1/jobs/share", json=payload)
        assert first.status_code == 200
        assert first.json()["duplicate"] is False

        second = await client.post("/api/v1/jobs/share", json=payload)
        assert second.status_code == 200
        data = second.json()
        assert data["duplicate"] is True
        assert data["job"]["url"] == payload["url"]

    @pytest.mark.asyncio
    async def test_share_job_auto_detects_meta_from_link(self, client):
        meta = {
            "title": "Senior VAPT Engineer",
            "site_name": "LinkedIn",
            "description": "Conduct penetration tests for enterprise clients.",
        }
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value=meta),
        ):
            resp = await client.post(
                "/api/v1/jobs/share",
                json={"url": "https://www.linkedin.com/jobs/view/vapt-12345"},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["job"]["title"] == "Senior VAPT Engineer"
        assert data["job"]["company"] == "LinkedIn"
        assert data["job"]["description"] == meta["description"]

    @pytest.mark.asyncio
    async def test_share_job_missing_title_returns_400(self, client):
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value={}),
        ):
            resp = await client.post(
                "/api/v1/jobs/share",
                json={"url": "https://example.com/unreadable-page"},
            )
        assert resp.status_code == 400
        assert "title" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_share_job_user_title_wins_over_meta(self, client):
        meta = {"title": "Generic Role", "site_name": "SomeBoard", "description": None}
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value=meta),
        ):
            resp = await client.post(
                "/api/v1/jobs/share",
                json={
                    "url": "https://example.com/x",
                    "title": "My Custom Title",
                    "company": "My Company",
                },
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["job"]["title"] == "My Custom Title"
        assert data["job"]["company"] == "My Company"

    @pytest.mark.asyncio
    async def test_share_job_blocks_internal_targets(self, client):
        """SSRF guard: private/internal URLs are never fetched (→ 400)."""
        resp = await client.post(
            "/api/v1/jobs/share",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert resp.status_code == 400
        assert "title" in resp.json()["detail"].lower()

        resp2 = await client.post(
            "/api/v1/jobs/share",
            json={"url": "http://localhost:8000/internal"},
        )
        assert resp2.status_code == 400

    @pytest.mark.asyncio
    async def test_share_job_normalizes_tracking_urls_for_dedup(self, client):
        """Tracking params/fragments/case don't create duplicate jobs."""
        base = "https://Example.com/jobs/42?utm_source=linkedin#frag"
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value={"title": "Bug Bounty", "site_name": "Board"}),
        ):
            first = await client.post("/api/v1/jobs/share", json={"url": base})
        assert first.status_code == 200
        assert first.json()["duplicate"] is False
        assert first.json()["job"]["url"] == "https://example.com/jobs/42"

        second = await client.post(
            "/api/v1/jobs/share",
            json={"url": "https://example.com/jobs/42"},
        )
        assert second.status_code == 200
        assert second.json()["duplicate"] is True

    @pytest.mark.asyncio
    async def test_share_job_uses_company_and_location_from_meta(self, client):
        """JSON-LD company + location now flow into the saved job."""
        meta = {
            "title": "SOC Analyst L2",
            "company": "Acme Security",
            "site_name": "Indeed",
            "location": "Bengaluru, Karnataka",
            "description": None,
        }
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value=meta),
        ):
            resp = await client.post(
                "/api/v1/jobs/share",
                json={"url": "https://in.indeed.com/viewjob?jk=abc123"},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # The hiring company (not the board's site_name) is used.
        assert data["job"]["company"] == "Acme Security"
        assert data["job"]["location"] == "Bengaluru, Karnataka"

    @pytest.mark.asyncio
    async def test_share_job_user_location_wins_over_meta(self, client):
        """A user-supplied location is never overwritten by the page meta."""
        meta = {
            "title": "SOC Analyst",
            "company": "Acme",
            "site_name": "Indeed",
            "location": "Mumbai, Maharashtra",
            "description": None,
        }
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value=meta),
        ):
            resp = await client.post(
                "/api/v1/jobs/share",
                json={
                    "url": "https://in.indeed.com/viewjob?jk=xyz789",
                    "title": "SOC Analyst",
                    "company": "Acme",
                    "location": "Bengaluru, Karnataka",
                },
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["job"]["location"] == "Bengaluru, Karnataka"

    @pytest.mark.asyncio
    async def test_share_job_company_falls_back_to_site_name(self, client):
        """JSON-LD title without a company falls back to og:site_name."""
        meta = {
            "title": "Senior VAPT Engineer",
            "site_name": "LinkedIn",
            "description": None,
        }
        with patch(
            "interntrack.api.v1.jobs._fetch_page_meta",
            new=AsyncMock(return_value=meta),
        ):
            resp = await client.post(
                "/api/v1/jobs/share",
                json={"url": "https://www.linkedin.com/jobs/view/vapt-67890"},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["job"]["company"] == "LinkedIn"


class TestParsePageMeta:
    """Pure HTML metadata extraction: JSON-LD > OpenGraph > <title>."""

    @staticmethod
    def _parse(html):
        from interntrack.api.v1.jobs import _parse_page_meta

        return _parse_page_meta(html)

    def test_json_ld_jobposting_wins_over_og(self):
        html = """
        <html><head>
          <meta property="og:title" content="Generic Role">
          <meta property="og:site_name" content="Indeed">
          <script type="application/ld+json">
          {"@type": "JobPosting", "title": "Application Security Engineer",
           "hiringOrganization": {"@type": "Organization", "name": "Zscaler"},
           "jobLocation": {"@type": "Place", "address": {
             "addressLocality": "Bengaluru", "addressRegion": "Karnataka"}}}
          </script>
        </head></html>
        """
        meta = self._parse(html)
        assert meta["title"] == "Application Security Engineer"
        assert meta["company"] == "Zscaler"
        assert meta["location"] == "Bengaluru, Karnataka"
        assert meta["site_name"] == "Indeed"

    def test_json_ld_in_list_with_other_types(self):
        html = """
        <html><head><script type="application/ld+json">[
          {"@type": "BreadcrumbList"},
          {"@type": "JobPosting", "title": "SOC Analyst",
           "hiringOrganization": {"name": "SecureCo"}}
        ]</script></head></html>
        """
        meta = self._parse(html)
        assert meta["title"] == "SOC Analyst"
        assert meta["company"] == "SecureCo"

    def test_og_fallback_without_json_ld(self):
        html = (
            "<html><head>"
            '<meta property="og:title" content="Penetration Tester">'
            '<meta property="og:site_name" content="LinkedIn">'
            '<meta property="og:description" content="VAPT for clients">'
            "</head></html>"
        )
        meta = self._parse(html)
        assert meta["title"] == "Penetration Tester"
        assert meta["site_name"] == "LinkedIn"
        assert meta["description"] == "VAPT for clients"
        assert "company" not in meta

    def test_html_title_fallback_when_no_meta(self):
        html = (
            "<html><head>"
            "<title>Vulnerability Researcher at CyberCorp</title>"
            "</head></html>"
        )
        meta = self._parse(html)
        assert meta["title"] == "Vulnerability Researcher at CyberCorp"
        assert "company" not in meta

    def test_empty_html_returns_no_title(self):
        meta = self._parse("<html><head></head><body></body></html>")
        assert meta["title"] is None
