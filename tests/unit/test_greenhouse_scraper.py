"""Tests for interntrack.scrapers.greenhouse."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestGreenhouseBoardScraper:
    @pytest.mark.asyncio
    def test_default_boards_include_verified_tech_employers(self):
        """The default board list covers the live-verified tech employers."""
        from interntrack.scrapers.greenhouse import GREENHOUSE_COMPANIES

        for company in ("elastic", "gitlab", "datadog", "mongodb", "zscaler"):
            assert company in GREENHOUSE_COMPANIES

    async def test_source_name(self):
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        scraper = GreenhouseBoardScraper(["okta"])
        assert scraper.source_name == "company"

    @pytest.mark.asyncio
    async def test_fetch_maps_and_filters_jobs(self):
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        scraper = GreenhouseBoardScraper(["okta", "cloudflare"])

        def job(title, location="Remote"):
            return {
                "title": title,
                "company_name": "TestCo",
                "absolute_url": f"https://boards.greenhouse.io/test/{title}",
                "location": {"name": location},
                "content": "<p>Security work</p>",
                "first_published": "2026-08-01T10:00:00+00:00",
                "application_deadline": None,
            }

        responses = [
            MagicMock(
                json=lambda: {"jobs": [job("Security Analyst"), job("Data Analyst")]}
            ),
            MagicMock(json=lambda: {"jobs": [job("SOC Analyst II")]}),
        ]
        scraper._get = AsyncMock(side_effect=responses)

        jobs = await scraper.fetch("security analyst")

        # Only security titles survive the matcher; Data Analyst is dropped.
        assert len(jobs) == 2
        assert all("Security" in j.title or "SOC" in j.title for j in jobs)
        assert jobs[0].company == "TestCo"
        assert jobs[0].source == "company"
        assert jobs[0].location == "Remote"
        assert jobs[0].posted_at is not None

    @pytest.mark.asyncio
    async def test_fetch_skips_failed_boards(self):
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        scraper = GreenhouseBoardScraper(["okta", "zscaler"])

        async def boom(url, **kwargs):
            if "zscaler" in url:
                raise RuntimeError("blocked")
            return MagicMock(json=lambda: {"jobs": [{"title": "Security Engineer"}]})

        scraper._get = boom

        jobs = await scraper.fetch("security")

        assert len(jobs) == 1
        assert jobs[0].title == "Security Engineer"

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        scraper = GreenhouseBoardScraper(["okta"])
        response = MagicMock(
            json=lambda: {
                "jobs": [
                    {"title": f"Security Role {i}", "location": {"name": "Remote"}}
                    for i in range(10)
                ]
            },
        )
        scraper._get = AsyncMock(return_value=response)

        jobs = await scraper.fetch("security", limit=3)

        assert len(jobs) == 3

    def test_clean_content_strips_html(self):
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        assert (
            GreenhouseBoardScraper._clean_content("<p>Hello <b>World</b></p>")
            == "Hello World"
        )
        assert GreenhouseBoardScraper._clean_content(None) == ""

    def test_parse_dt(self):
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        dt = GreenhouseBoardScraper._parse_dt("2026-08-01T10:00:00+00:00")
        assert dt is not None
        assert dt.year == 2026
        assert GreenhouseBoardScraper._parse_dt(None) is None
        assert GreenhouseBoardScraper._parse_dt("not-a-date") is None
