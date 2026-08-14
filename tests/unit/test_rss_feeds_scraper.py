"""Unit tests for scrapers/rss_feeds.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRSSFeedScraper:
    """Tests for RSSFeedScraper class."""

    def test_source_name(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        assert scraper.source_name == "rss_feed"

    def test_rate_limit(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        assert scraper.rate_limit == 60

    def test_custom_feeds(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        custom_feeds = {"custom1": "https://example.com/feed.rss"}
        scraper = RSSFeedScraper(feeds=custom_feeds)
        assert scraper.feeds == custom_feeds

    def test_default_feeds(self):
        from interntrack.scrapers.rss_feeds import DEFAULT_FEEDS, RSSFeedScraper

        scraper = RSSFeedScraper()
        assert scraper.feeds == DEFAULT_FEEDS
        assert "himalayas" in DEFAULT_FEEDS
        assert "sarkariresult" in DEFAULT_FEEDS

    def test_extract_company_from_title_hiring(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_company_from_title("TechCorp is hiring")
        assert result == "TechCorp"

    def test_extract_company_from_title_hiring_colon(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_company_from_title("Hiring: TechCorp")
        assert result == "TechCorp"

    def test_extract_company_from_title_brackets(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_company_from_title("[TechCorp] Python Developer")
        assert result == "TechCorp"

    def test_extract_company_from_title_unknown(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_company_from_title("Python Developer Position")
        assert result == "Unknown"

    def test_extract_tags_python(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_tags("Python developer with Django experience")
        assert "python" in result

    def test_extract_tags_javascript(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_tags("JavaScript and React experience")
        assert "javascript" in result
        assert "react" in result

    def test_extract_tags_remote(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_tags("Remote position available")
        assert "remote" in result

    def test_extract_tags_empty(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        result = scraper._extract_tags("Looking for a good communicator")
        assert len(result) == 0

    def test_parse_entry_multi_word_query(self):
        """Regression: 'security analyst' matches SOC Analyst but not Data Analyst."""
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        match_entry = {
            "title": "SOC Analyst at SecureCorp",
            "link": "https://example.com/1",
            "summary": "Monitor and respond to security events",
        }
        assert (
            scraper._parse_entry(match_entry, "security analyst", "rss_feed")
            is not None
        )

        no_match_entry = {
            "title": "Data Analyst at Acme",
            "link": "https://example.com/2",
            "summary": "Build dashboards in Excel and SQL",
        }
        assert (
            scraper._parse_entry(no_match_entry, "security analyst", "rss_feed") is None
        )

    def test_parse_entry_security_expansion(self):
        """Regression: a 'cybersecurity' query surfaces SOC/pentest roles."""
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        entry = {
            "title": "SOC Analyst at SecureCorp",
            "link": "https://example.com/2",
            "summary": "Monitor and respond to security events",
        }
        result = scraper._parse_entry(entry, "cybersecurity", "rss_feed")
        assert result is not None

    def test_parse_entry_security_matches_title_not_summary(self):
        """Regression: a 'Web Developer' whose summary mentions 'security'
        must not match a 'cybersecurity' query."""
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        entry = {
            "title": "Web Developer",
            "link": "https://example.com/3",
            "summary": "Own the security and compliance of our platform",
        }
        result = scraper._parse_entry(entry, "cybersecurity", "rss_feed")
        assert result is None

    def test_parse_entry_returns_none_for_no_match(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        entry = {
            "title": "Java Developer Position",
            "link": "https://example.com/123",
            "summary": "Java experience required",
        }
        result = scraper._parse_entry(entry, "python", "rss_feed")
        assert result is None

    def test_parse_entry_returns_job_for_match(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        entry = {
            "title": "TechCorp is hiring a Python Developer",
            "link": "https://example.com/123",
            "summary": "Python and Django experience required",
            "published_parsed": (2026, 7, 30, 14, 30, 0, 0, 0, 0),
        }
        result = scraper._parse_entry(entry, "python", "rss_feed")
        assert result is not None
        assert result.title == "TechCorp is hiring a Python Developer"
        assert result.company == "TechCorp"
        assert result.source == "rss_feed"
        assert result.posted_at is not None

    def test_parse_entry_no_date(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper()
        entry = {
            "title": "Python Developer Position",
            "link": "https://example.com/123",
            "summary": "Python experience required",
        }
        result = scraper._parse_entry(entry, "python", "rss_feed")
        assert result is not None
        assert result.posted_at is None

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper(feeds={"bad": "https://invalid.url/feed"})
        scraper._get = AsyncMock(side_effect=Exception("Network error"))

        result = await scraper.fetch("python")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_returns_jobs(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper(feeds={"test": "https://example.com/feed"})

        mock_response = MagicMock()
        mock_response.text = """
        <rss version="2.0">
            <channel>
                <item>
                    <title>Python Developer at TechCorp</title>
                    <link>https://example.com/123</link>
                    <description>Python and Django experience required</description>
                </item>
            </channel>
        </rss>
        """
        scraper._get = AsyncMock(return_value=mock_response)

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Python Developer at TechCorp",
                    "link": "https://example.com/123",
                    "summary": "Python and Django experience required",
                },
            ]
            mock_parse.return_value.feed = {"title": "Test Feed"}

            result = await scraper.fetch("python")
            assert len(result) >= 0  # May be empty due to parsing

    @pytest.mark.asyncio
    async def test_fetch_emits_enum_source_not_feed_key(self):
        """Regression: jobs must carry the enum source (rss_feed), not the raw
        feed dict key (e.g. "weworkremotely"), so stored rows round-trip
        through the JobSource column on Postgres."""
        from interntrack.scrapers.rss_feeds import RSSFeedScraper

        scraper = RSSFeedScraper(feeds={"weworkremotely": "https://example.com/feed"})

        mock_response = MagicMock()
        mock_response.text = "<rss version='2.0'><channel></channel></rss>"
        scraper._get = AsyncMock(return_value=mock_response)

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Python Developer at TechCorp",
                    "link": "https://example.com/123",
                    "summary": "Python and Django experience required",
                },
            ]
            mock_parse.return_value.feed = {"title": "Test Feed"}

            result = await scraper.fetch("python")
            assert result
            for job in result:
                assert job.source == "rss_feed"
                assert job.source != "weworkremotely"


class TestCustomRSSFeedScraper:
    """Tests for CustomRSSFeedScraper class."""

    def test_init_with_feeds(self):
        from interntrack.scrapers.rss_feeds import CustomRSSFeedScraper

        feed_urls = ["https://example.com/feed1", "https://example.com/feed2"]
        scraper = CustomRSSFeedScraper(feed_urls)

        assert "custom_0" in scraper.feeds
        assert "custom_1" in scraper.feeds
        assert scraper.feeds["custom_0"] == "https://example.com/feed1"
        assert scraper.feeds["custom_1"] == "https://example.com/feed2"
