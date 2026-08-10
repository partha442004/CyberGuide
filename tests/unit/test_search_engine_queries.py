"""Unit tests for the search-engine scraper's query generation.

The scraper is a discovery net that asks DuckDuckGo/Bing for ``site:``
queries per board. These tests lock the query list so India-focused boards
(Naukri, Shine, Freshersworld, Unstop, Cutshort, Wellfound, Foundit,
TimesJobs, Hirect) keep getting surfaced even as the scraper evolves.
"""

import pytest

from interntrack.scrapers.search_engine import SearchEngineScraper


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
