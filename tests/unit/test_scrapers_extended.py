"""Extended unit tests for scraper implementations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Base Scraper ───────────────────────────────────────────────────────────

class TestBaseScraper:
    """Tests for BaseScraper."""

    def test_raw_job_creation(self):
        from interntrack.scrapers.base import RawJob

        job = RawJob(title="Dev", company="Co", url="https://example.com")
        assert job.title == "Dev"
        assert job.company == "Co"
        assert job.tags == []
        assert job.source == "unknown"
        assert job.is_remote is False

    def test_raw_job_to_dict(self):
        from interntrack.scrapers.base import RawJob

        job = RawJob(title="Dev", company="Co", url="https://example.com")
        d = job.to_dict()
        assert d["title"] == "Dev"
        assert d["company"] == "Co"
        assert "tags" in d
        assert "source" in d

    def test_raw_job_all_fields(self):
        from interntrack.scrapers.base import RawJob

        job = RawJob(
            title="Dev", company="Co", url="https://example.com",
            description="Desc", location="Remote", salary_min=80000,
            salary_max=120000, salary_currency="EUR", job_type="full_time",
            is_remote=True, tags=["python"], source="test", raw_data={"key": "val"},
        )
        d = job.to_dict()
        assert d["salary_currency"] == "EUR"
        assert d["is_remote"] is True
        assert d["raw_data"] == {"key": "val"}


# ─── RemoteOK Scraper ──────────────────────────────────────────────────────

class TestRemoteOKScraper:
    """Tests for RemoteOKScraper."""

    def test_source_name(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        assert scraper.source_name == "remote_ok"

    def test_rate_limit(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        assert scraper.rate_limit == 30

    def test_parse_salary_range(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        min_s, max_s = scraper._parse_salary("$80,000 - $120,000")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_single(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        min_s, max_s = scraper._parse_salary("$100,000")
        assert min_s == 100000
        assert max_s == 100000

    def test_parse_salary_none(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        min_s, max_s = scraper._parse_salary("Competitive")
        assert min_s is None
        assert max_s is None

    def test_parse_salary_empty(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        min_s, max_s = scraper._parse_salary("")
        assert min_s is None
        assert max_s is None

    def test_parse_date_valid(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        result = scraper._parse_date(1700000000)
        assert result is not None

    def test_parse_date_none(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        assert scraper._parse_date(None) is None

    def test_parse_job_matches_query(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        item = {
            "position": "Python Developer",
            "company": "TechCorp",
            "description": "Build APIs",
            "url": "https://example.com",
            "location": "Remote",
            "tags": ["python"],
        }
        job = scraper._parse_job(item, "python")
        assert job is not None
        assert job.title == "Python Developer"

    def test_parse_job_no_match(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        item = {
            "position": "Java Developer",
            "company": "TechCorp",
            "description": "Build Java apps",
        }
        job = scraper._parse_job(item, "python")
        assert job is None

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"metadata": True},
            {
                "position": "Python Dev",
                "company": "Co",
                "description": "Python role",
                "id": "123",
            },
        ]

        scraper._get = AsyncMock(return_value=mock_response)

        jobs = await scraper.fetch("python", limit=5)

        assert len(jobs) == 1
        assert jobs[0].title == "Python Dev"

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        scraper = RemoteOKScraper()
        scraper._get = AsyncMock(side_effect=Exception("Network error"))

        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── RSS Feed Scraper ──────────────────────────────────────────────────────

class TestRSSFeedScraper:
    """Tests for RSSFeedScraper."""

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
        feeds = {"custom": "https://example.com/rss"}
        scraper = RSSFeedScraper(feeds=feeds)
        assert scraper.feeds == feeds

    def test_extract_company_hiring(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        assert scraper._extract_company_from_title("TechCorp is hiring") == "TechCorp"

    def test_extract_company_brackets(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        assert scraper._extract_company_from_title("[Google] Python Dev") == "Google"

    def test_extract_company_unknown(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        assert scraper._extract_company_from_title("Random Title") == "Unknown"

    def test_extract_tags(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        tags = scraper._extract_tags("Python and React developer needed")
        assert "python" in tags
        assert "react" in tags

    def test_extract_tags_none(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        tags = scraper._extract_tags("General position")
        assert tags == []

    def test_parse_entry_matches_query(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        entry = {
            "title": "Python Developer at TechCorp",
            "link": "https://example.com",
            "summary": "Build APIs with Python",
        }
        job = scraper._parse_entry(entry, "python", "rss_feed")
        assert job is not None
        assert "Python" in job.title

    def test_parse_entry_no_match(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        entry = {
            "title": "Java Developer",
            "link": "https://example.com",
            "summary": "Build Java apps",
        }
        job = scraper._parse_entry(entry, "python", "rss_feed")
        assert job is None

    def test_parse_entry_with_date(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()
        entry = {
            "title": "Python Dev",
            "link": "https://example.com",
            "summary": "Python role",
            "published_parsed": (2026, 1, 15, 10, 0, 0, 0, 0, 0),
        }
        job = scraper._parse_entry(entry, "python", "rss_feed")
        assert job is not None
        assert job.posted_at is not None

    @pytest.mark.asyncio
    async def test_fetch_feed_success(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        scraper = RSSFeedScraper()

        mock_response = MagicMock()
        mock_response.text = "<rss><channel></channel></rss>"
        scraper._get = AsyncMock(return_value=mock_response)

        with patch("interntrack.scrapers.rss_feeds.feedparser") as mock_feed:
            mock_feed.parse.return_value.entries = []
            jobs = await scraper._fetch_feed("https://example.com/rss", "python", "test")

        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_multiple_feeds(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        feeds = {"f1": "https://a.com/rss", "f2": "https://b.com/rss"}
        scraper = RSSFeedScraper(feeds=feeds)

        mock_response = MagicMock()
        mock_response.text = "<rss></rss>"
        scraper._get = AsyncMock(return_value=mock_response)

        with patch("interntrack.scrapers.rss_feeds.feedparser") as mock_feed:
            mock_feed.parse.return_value.entries = []
            jobs = await scraper.fetch("python", limit=10)

        assert jobs == []


class TestCustomRSSFeedScraper:
    """Tests for CustomRSSFeedScraper."""

    def test_init(self):
        from interntrack.scrapers.rss_feeds import CustomRSSFeedScraper
        scraper = CustomRSSFeedScraper(["https://a.com/rss", "https://b.com/rss"])
        assert "custom_0" in scraper.feeds
        assert "custom_1" in scraper.feeds
        assert scraper.feeds["custom_0"] == "https://a.com/rss"
