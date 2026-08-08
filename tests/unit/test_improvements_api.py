"""
Tests for the improvement batch — watchlists, per-user applications,
per-user discovery queries, the styled HTML digest and the personalized
dashboard overview.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


class TestWatchlistAPI:
    """Company watchlist endpoints."""

    @pytest.mark.asyncio
    async def test_add_and_list_watchlist(self, client):
        add = await client.post(
            "/api/v1/watchlists",
            json={"user_id": "u-1", "company": "CrowdStrike"},
        )
        assert add.status_code == 201, add.text
        await client.post(
            "/api/v1/watchlists",
            json={"user_id": "u-1", "company": "Palo Alto"},
        )
        # Another user's watchlist is separate.
        await client.post(
            "/api/v1/watchlists",
            json={"user_id": "u-2", "company": "Google"},
        )

        listing = await client.get("/api/v1/watchlists?user_id=u-1")
        assert listing.status_code == 200
        data = listing.json()
        companies = {item["company"] for item in data["watchlist"]}
        assert companies == {"CrowdStrike", "Palo Alto"}
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_duplicate_watchlist_conflict(self, client):
        await client.post(
            "/api/v1/watchlists",
            json={"user_id": "u-1", "company": "CrowdStrike"},
        )
        dup = await client.post(
            "/api/v1/watchlists",
            json={"user_id": "u-1", "company": "CrowdStrike"},
        )
        assert dup.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_watchlist(self, client):
        add = await client.post(
            "/api/v1/watchlists",
            json={"user_id": "u-1", "company": "Fortinet"},
        )
        watch_id = add.json()["id"]
        delete = await client.delete(f"/api/v1/watchlists/{watch_id}")
        assert delete.status_code == 204
        listing = await client.get("/api/v1/watchlists?user_id=u-1")
        assert listing.json()["total"] == 0
        missing = await client.delete("/api/v1/watchlists/does-not-exist")
        assert missing.status_code == 404


class TestPerUserApplications:
    """Applications are scoped per user."""

    @pytest.mark.asyncio
    async def test_create_application_with_user_and_dedupe(self, client):
        first = await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-1", "user_id": "u-1"},
        )
        assert first.status_code == 201
        assert first.json()["user_id"] == "u-1"

        # Same user + job is idempotent (returns the existing application).
        second = await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-1", "user_id": "u-1"},
        )
        assert second.status_code == 201
        assert second.json()["id"] == first.json()["id"]

        # A different user can apply to the same job separately.
        third = await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-1", "user_id": "u-2"},
        )
        assert third.status_code == 201
        assert third.json()["id"] != first.json()["id"]

    @pytest.mark.asyncio
    async def test_list_applications_filtered_by_user(self, client):
        await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-a", "user_id": "u-1"},
        )
        await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-b", "user_id": "u-1"},
        )
        await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-c", "user_id": "u-2"},
        )

        mine = await client.get("/api/v1/applications/?user_id=u-1")
        assert mine.status_code == 200
        job_ids = {a["job_id"] for a in mine.json()["applications"]}
        assert job_ids == {"job-a", "job-b"}

    @pytest.mark.asyncio
    async def test_metrics_scoped_to_user(self, client):
        await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-a", "user_id": "u-1"},
        )
        await client.post(
            "/api/v1/applications/",
            json={"job_id": "job-b", "user_id": "u-2"},
        )
        mine = await client.get("/api/v1/applications/metrics/overview?user_id=u-1")
        assert mine.status_code == 200
        assert mine.json()["total_applications"] == 1


class TestDiscoveryQueries:
    """discovery_queries_for derives searches from domains + skills."""

    def test_domain_queries(self):
        from interntrack.scheduler.jobs import discovery_queries_for

        # limit=30 (not the default 4) so the assertions don't silently
        # depend on vapt/cybersecurity staying in the top-4 slots.
        queries = discovery_queries_for({"domains": ["security"]}, limit=30)
        assert any("cybersecurity" in q for q in queries)
        assert any("vapt" in q for q in queries)

    def test_security_queries_cover_modern_roles(self):
        """Security discovery covers SOC/IR/devsecops, not just VAPT."""
        from interntrack.scheduler.jobs import discovery_queries_for

        queries = discovery_queries_for({"domains": ["security"]}, limit=30)
        assert any("security engineer" in q for q in queries)
        assert any("incident response" in q for q in queries)
        assert any("devsecops" in q for q in queries)
        assert any("cyber defense" in q for q in queries)

    def test_coding_queries_cover_backend_roles(self):
        """Coding discovery actively searches backend-focused roles."""
        from interntrack.scheduler.jobs import discovery_queries_for

        queries = discovery_queries_for({"domains": ["coding"]}, limit=30)
        assert any("backend developer" in q for q in queries)
        assert any("backend engineer" in q for q in queries)
        assert any("java developer" in q for q in queries)
        assert any("microservices" in q for q in queries)
        assert any("api developer" in q for q in queries)

    def test_skills_added_as_intern_queries(self):
        from interntrack.scheduler.jobs import discovery_queries_for

        user = SimpleNamespace(skills=["burp suite", "nmap"])
        queries = discovery_queries_for({"domains": ["security"]}, user=user, limit=30)
        assert any("burp suite intern" in q for q in queries)
        assert any("nmap intern" in q for q in queries)

    def test_deduplicated_and_limited(self):
        from interntrack.scheduler.jobs import discovery_queries_for

        queries = discovery_queries_for({"domains": ["security"]}, limit=2)
        assert len(queries) == 2
        assert len(set(queries)) == len(queries)

    def test_no_domains_uses_other_fallback(self):
        from interntrack.scheduler.jobs import discovery_queries_for

        queries = discovery_queries_for({"domains": []})
        assert queries  # non-empty

    def test_location_queries_survive_limit_cap(self):
        """With a location set, Bangalore-suffixed queries come FIRST so the
        [:limit] cap keeps them instead of plain keywords."""
        from interntrack.scheduler.jobs import discovery_queries_for

        user = SimpleNamespace(skills=[], location="Bangalore")
        queries = discovery_queries_for(
            {"domains": ["security"]},
            user=user,
            limit=4,
        )
        assert len(queries) == 4
        assert all("Bangalore" in q for q in queries)

    def test_location_extraction_from_query(self):
        """Discovery queries like 'cybersecurity bangalore' resolve the city."""
        from interntrack.api.v1.jobs import _extract_location_from_query

        assert _extract_location_from_query("cybersecurity bangalore") == "Bangalore"
        assert _extract_location_from_query("python developer mumbai") == "Mumbai"
        assert _extract_location_from_query("soc analyst bengaluru") == "Bangalore"
        assert _extract_location_from_query("devops engineer") is None


class TestPerUserDiscoveryEndpoint:
    """POST /jobs/discovery/run-for-users derives queries per user."""

    @pytest.mark.asyncio
    async def test_runs_discovery_for_enabled_users(self):
        from interntrack.api.v1.jobs import run_discovery_for_users

        targets = [
            {
                "user_id": "u1",
                "prefs": {"domains": ["security"], "is_enabled": True},
                "user": SimpleNamespace(skills=["vapt"]),
            }
        ]
        registry = AsyncMock()
        registry.fetch_all.return_value = [{"title": "X", "company": "C"}]

        with (
            patch(
                "interntrack.scheduler.jobs._enabled_alert_targets",
                new=AsyncMock(return_value=targets),
            ),
            patch(
                "interntrack.scrapers.registry.get_default_registry",
                return_value=registry,
            ),
            patch("interntrack.api.v1.jobs.JobService") as job_cls,
        ):
            job_cls.return_value.save_jobs = AsyncMock(return_value=[{}])
            result = await run_discovery_for_users(db=AsyncMock(), limit=4)

        assert result["users"] == 1
        assert result["queries_run"] >= 2  # security domains + vapt intern
        assert result["found"] >= 1
        assert result["saved"] >= 1

    @pytest.mark.asyncio
    async def test_no_users_falls_back_to_fixed_queries(self):
        from interntrack.api.v1.jobs import run_discovery_for_users

        registry = AsyncMock()
        registry.fetch_all.return_value = []

        with (
            patch(
                "interntrack.scheduler.jobs._enabled_alert_targets",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "interntrack.scrapers.registry.get_default_registry",
                return_value=registry,
            ),
            patch("interntrack.api.v1.jobs.JobService") as job_cls,
        ):
            job_cls.return_value.save_jobs = AsyncMock(return_value=[])
            result = await run_discovery_for_users(db=AsyncMock(), limit=4)

        assert result["users"] == 0
        assert result["queries_run"] == 3  # classic fallback queries


class TestHtmlDigest:
    """build_daily_report_html renders a styled, escaped digest."""

    @pytest.mark.asyncio
    async def test_html_has_sections_and_escapes_content(self):
        from interntrack.scheduler.jobs import build_daily_report_html

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "generated_at": "2026-08-05",
            "new_jobs": [
                {
                    "title": "Security Engineer <script>",
                    "company": "Acme & Sons",
                    "url": "https://acme.example/apply",
                    "location": "Remote",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": False,
                }
            ],
        }

        html = await build_daily_report_html(report, None)
        assert "Security Engineer" in html
        # Untrusted content is escaped.
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "Acme &amp; Sons" in html
        # Apply button links to the listing.
        assert "Apply now" in html
        assert "https://acme.example/apply" in html
        # Domain section header present.
        assert "Cybersecurity / VAPT / SOC" in html

    @pytest.mark.asyncio
    async def test_team_section_renders_when_present(self):
        """The weekly email's team snapshot renders only when attached."""
        from interntrack.scheduler.jobs import build_daily_report_html

        base = {"summary": {"new_jobs": 0, "new_applications": 0}}
        # No team key -> no section.
        html = await build_daily_report_html(base, None)
        assert "Your team" not in html
        # With team key -> section with size and referrals.
        html = await build_daily_report_html(
            {**base, "team": {"team_size": 4, "my_referrals": 2}},
            None,
        )
        assert "Your team" in html
        assert ">4<" in html
        assert "joined through <b>your</b> invite link" in html
        # Zero referrals -> no referral sentence.
        html = await build_daily_report_html(
            {**base, "team": {"team_size": 4, "my_referrals": 0}},
            None,
        )
        assert "Your team" in html
        assert "invite link" not in html

    @pytest.mark.asyncio
    async def test_watched_companies_section(self):
        from interntrack.scheduler.jobs import build_daily_report_html

        class FakeSession:
            async def execute(self, query, *args, **kwargs):
                class Result:
                    def all(self):
                        return [("Crowdstrike",)]

                    def scalar_one_or_none(self):
                        return None

                    def scalars(self):
                        return self

                return Result()

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "generated_at": "2026-08-05",
            "new_jobs": [
                {
                    "title": "Threat Analyst",
                    "company": "CrowdStrike",
                    "url": "https://x/apply",
                    "age_days": 0,
                }
            ],
        }
        html = await build_daily_report_html(report, FakeSession(), user_id="u-1")
        assert "Watched companies" in html
