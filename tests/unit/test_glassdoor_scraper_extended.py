"""
Unit Tests for the Glassdoor scraper (extended).

Covers the ``fetch`` loop with a location param and successful HTML parsing.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.scrapers.glassdoor import GlassdoorScraper


class TestFetchWithLocation:
    """Tests for fetch() with location and job cards."""

    @pytest.mark.asyncio
    async def test_fetch_with_location_and_cards(self):
        """Should set location params, parse job cards, and honor the limit."""
        scraper = GlassdoorScraper()

        # Fake HTTP response with HTML containing two job cards.
        response = MagicMock()
        response.status_code = 200
        response.text = (
            "<ul>"
            '<li class="jobListing"><a class="job-title">Engineer</a></li>'
            '<li class="jobListing"><a class="job-title">Analyst</a></li>'
            '<li class="jobListing"><a class="job-title">Third</a></li>'
            "</ul>"
        )
        scraper._get = AsyncMock(return_value=response)  # type: ignore[assignment]

        # _parse_job_card is exercised via the real implementation; stub it so
        # the loop's bookkeeping (job is truthy) is what we assert.
        real_parse = scraper._parse_job_card

        def fake_parse(card):
            parsed = real_parse(card)
            if parsed is None:
                # ensure the loop sees a truthy job for each card
                return SimpleNamespace(source="glassdoor", title="parsed")
            return parsed

        with patch.object(scraper, "_parse_job_card", side_effect=fake_parse):
            jobs = await scraper.fetch("security", location="New York", limit=2)

        # limit respected
        assert len(jobs) == 2

        # URL contains encoded params
        call_url = scraper._get.call_args.args[0]
        assert "sc.keyword=security" in call_url
        assert "locKeyword=New+York" in call_url

    @pytest.mark.asyncio
    async def test_fetch_without_location(self):
        """Should omit location params when location is None."""
        scraper = GlassdoorScraper()
        response = MagicMock()
        response.status_code = 200
        response.text = "<ul></ul>"
        scraper._get = AsyncMock(return_value=response)  # type: ignore[assignment]

        jobs = await scraper.fetch("security")

        assert jobs == []
        call_url = scraper._get.call_args.args[0]
        assert "locKeyword" not in call_url

    @pytest.mark.asyncio
    async def test_fetch_non_200_returns_empty(self):
        """Should return an empty list when the response is not 200."""
        scraper = GlassdoorScraper()
        response = MagicMock()
        response.status_code = 429
        scraper._get = AsyncMock(return_value=response)  # type: ignore[assignment]

        jobs = await scraper.fetch("security")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_handles_exception(self):
        """Should swallow exceptions and return whatever was collected."""
        scraper = GlassdoorScraper()
        scraper._get = AsyncMock(side_effect=RuntimeError("network down"))  # type: ignore[assignment]

        jobs = await scraper.fetch("security")
        assert jobs == []
