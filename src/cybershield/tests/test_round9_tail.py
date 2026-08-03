"""
Round 9 tail tests covering the final small uncovered branches:

- ``cybershield/config.py`` (channel configuration properties)
- ``scrapers/worldwide/rss_feeds.py`` (job/security feed flags)
- ``interntrack/main.py`` (rate-limit middleware registration)
- ``interntrack/scrapers/linkedin.py`` (location query param)
- ``scrapers/usa/indeed.py`` (viewjob job-id regex)
- ``scrapers/usa/linkedin.py`` (title \" at \" with no location)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestCybershieldConfigProperties:
    """Channel configuration helper properties."""

    def _settings(self, **overrides):
        from typing import Any

        from cybershield.config import Settings

        defaults: dict[str, Any] = {
            "telegram_bot_token": None,
            "telegram_chat_id": None,
            "discord_webhook_url": None,
            "slack_webhook_url": None,
            "smtp_user": None,
            "smtp_password": None,
            "gemini_api_key": None,
            "ollama_base_url": "",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def test_telegram_configured(self):
        assert self._settings().is_telegram_configured is False
        assert (
            self._settings(telegram_bot_token="t", telegram_chat_id="c").is_telegram_configured
            is True
        )

    def test_discord_configured(self):
        assert self._settings().is_discord_configured is False
        assert self._settings(discord_webhook_url="https://discord/x").is_discord_configured is True

    def test_slack_configured(self):
        assert self._settings().is_slack_configured is False
        assert self._settings(slack_webhook_url="https://slack/x").is_slack_configured is True

    def test_email_configured(self):
        assert self._settings().is_email_configured is False
        assert self._settings(smtp_user="u", smtp_password="p").is_email_configured is True

    def test_ai_configured(self):
        assert self._settings().is_ai_configured is False
        assert self._settings(gemini_api_key="k").is_ai_configured is True
        assert self._settings(ollama_base_url="http://localhost:11434").is_ai_configured is True


class TestRssFeedsRound9:
    """feed selection flags in the RSS feeds scraper."""

    @pytest.mark.asyncio
    async def test_scrape_with_job_and_security_feeds(self):
        from cybershield.scrapers.worldwide.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        # Patch the feed maps and the per-feed fetch so no network happens.
        scraper.JOB_FEEDS = {"jobfeed": "https://jobs.example/rss"}
        scraper.SECURITY_FEEDS = {"secfeed": "https://sec.example/rss"}
        fetched = set()

        async def fake_fetch(url, **kwargs):
            fetched.add(url)
            response = MagicMock()
            response.text = "<rss><channel></channel></rss>"
            return response

        scraper._fetch = AsyncMock(side_effect=fake_fetch)  # type: ignore[method-assign]

        await scraper.scrape(
            feeds={},
            include_job_feeds=True,
            include_security_feeds=True,
        )

        assert "https://jobs.example/rss" in fetched
        assert "https://sec.example/rss" in fetched

    @pytest.mark.asyncio
    async def test_scrape_with_custom_feeds_only(self):
        from cybershield.scrapers.worldwide.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        scraper.JOB_FEEDS = {"jobfeed": "https://jobs.example/rss"}
        scraper.SECURITY_FEEDS = {"secfeed": "https://sec.example/rss"}
        fetched = set()

        async def fake_fetch(url, **kwargs):
            fetched.add(url)
            response = MagicMock()
            response.text = "<rss><channel></channel></rss>"
            return response

        scraper._fetch = AsyncMock(side_effect=fake_fetch)  # type: ignore[method-assign]

        # include_job_feeds/security disabled -> only the custom feed runs.
        await scraper.scrape(
            feeds={"custom": "https://custom.example/rss"},
            include_job_feeds=False,
            include_security_feeds=False,
        )

        assert fetched == {"https://custom.example/rss"}


class TestInterntrackLinkedinRound9:
    """fetch() adds the location query param when provided."""

    @pytest.mark.asyncio
    async def test_fetch_with_location(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        scraper._get = AsyncMock(return_value=MagicMock())  # type: ignore[method-assign]

        await scraper.fetch("security", location="Pune")

        kwargs = scraper._get.await_args.kwargs  # type: ignore[union-attr]
        params = kwargs.get("params", {})
        assert params.get("location") == "Pune"


class TestUsaIndeedTail:
    """viewjob job-id extraction via the second regex."""

    def test_extract_job_id_viewjob_non_hex(self):
        from cybershield.scrapers.usa.indeed import IndeedScraper

        scraper = IndeedScraper()
        # A jk= value with no leading hex chars skips the first regex and
        # falls through to the /viewjob regex branch.
        assert scraper._extract_job_id("https://indeed.com/viewjob?jk=XYZ789") == "XYZ789"


class TestLinkedinTail:
    """Title \"Job at Company\" (no location) keeps tail as company."""

    def test_title_at_without_location(self):
        from cybershield.scrapers.usa.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        job = scraper._parse_feed_entry(
            {
                "title": "Security Engineer at Acme Corp",
                "link": "https://linkedin.com/jobs/view/1",
                "summary": "",
            }
        )
        assert job is not None
        assert job.company_name == "Acme Corp"
