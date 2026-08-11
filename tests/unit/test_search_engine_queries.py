"""Unit tests for the search-engine scraper's query generation.

The scraper is a discovery net that asks DuckDuckGo/Bing for ``site:``
queries per board. These tests lock the query list so India-focused boards
(Naukri, Shine, Freshersworld, Unstop, Cutshort, Wellfound, Foundit,
TimesJobs, Hirect) keep getting surfaced even as the scraper evolves.
"""

import pytest

from interntrack.scrapers.search_engine import SearchEngineScraper


class _FakeResponse:
    """Minimal page response for the scraper's ``_get`` calls."""

    status_code = 200

    def __init__(self, text: str = ""):
        self.text = text


async def _fake_get(url: str, timeout: int = 10):  # noqa: ARG001 - scraper API shape
    """Fake ``_get`` returning a parseable job page for any URL."""
    return _FakeResponse(
        "<html><head>"
        "<meta property='og:title' content='Security Engineer'>"
        "<meta property='og:site_name' content='SecureCo'>"
        "</head></html>"
    )


class TestSearchEngineQueries:
    """Tests for the generated search queries."""

    @pytest.mark.asyncio
    async def test_includes_indian_job_boards(self):
        """Naukri + friends must appear in the site: query list."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        jobs = await scraper.fetch("cybersecurity", "Bangalore", limit=8)

        assert jobs == []
        assert seen, "scraper never issued a query"
        joined = " ".join(seen)
        # Every India-focused board in _JOB_HOSTS must be queryable.
        for host in (
            "site:naukri.com",
            "site:shine.com",
            "site:freshersworld.com",
            "site:unstop.com",
            "site:cutshort.io",
            "site:wellfound.com",
            "site:foundit.in",
            "site:timesjobs.com",
            "site:hirect.in",
            # Cybersecurity-specific boards.
            "site:cybersecurityjobs.com",
            "site:cybersecurityjobsite.com",
            "site:cybersn.com",
            "site:clearedjobs.net",
            "site:infosec-jobs.com",
            "site:securityjobs.net",
            "site:ninjajobs.com",
            "site:techfetch.com",
        ):
            assert host in joined, f"missing {host} in search queries"

    @pytest.mark.asyncio
    async def test_location_appended_to_query(self):
        """Location is folded into the base query so results are city-scoped."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("soc analyst", "Chennai", limit=8)

        assert seen
        assert any("soc analyst chennai" in q.lower() for q in seen)

    @pytest.mark.asyncio
    async def test_generic_query_kept_first(self):
        """The plain 'job OR vacancy' query runs first (broad net)."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("frontend", "Pune", limit=8)

        assert seen
        assert "job or vacancy or opening" in seen[0].lower()

    @pytest.mark.asyncio
    async def test_linkedin_surface_queries(self):
        """LinkedIn is auth-walled from datacenter IPs — the search engine
        must carry explicit ``site:linkedin.com/jobs`` queries so posting
        URLs still surface and the biggest source stays fresh."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("security", "Bangalore", limit=8)

        assert seen
        joined = " ".join(seen)
        assert "site:linkedin.com/jobs" in joined
        assert "site:in.linkedin.com/jobs" in joined
        # The query still carries the domain + location context.
        assert any("security" in q.lower() and "bangalore" in q.lower() for q in seen)

    @pytest.mark.asyncio
    async def test_per_query_budget_keeps_board_queries_live(self):
        """A productive generic query must not eat the whole limit — each
        board-specific ``site:`` query keeps its own slice, so LinkedIn /
        Naukri / cyber-board postings still surface even when the first
        query returns jobs."""
        scraper = SearchEngineScraper()
        calls: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            calls.append(query)
            # Only the generic query "job OR vacancy" returns any links;
            # if the budget works, the loop still moves on to the later
            # site: queries instead of stopping at the limit.
            if "job or vacancy" in query.lower():
                return [
                    "https://www.linkedin.com/jobs/view/123",
                    "https://www.linkedin.com/jobs/view/124",
                    "https://www.linkedin.com/jobs/view/125",
                ]
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        scraper._get = _fake_get  # type: ignore[method-assign]
        await scraper.fetch("security", "Bangalore", limit=8)

        joined = " ".join(calls)
        # The board-specific queries must still have been issued even though
        # the generic one produced (3) jobs — per-query budget keeps them.
        assert "site:linkedin.com/jobs" in joined
        assert "site:naukri.com" in joined
        assert "site:cybersecurityjobs.com" in joined
