"""Unified scraper tests — consolidates all scraper unit tests into one file.

Covers: BaseScraper, HackerNews, LinkedIn, Indeed, Glassdoor, RemoteOK, RSS Feeds.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Base Scraper ────────────────────────────────────────────────────────────


class TestBaseScraper:
    """Tests for BaseScraper and RawJob."""

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
            is_remote=True, tags=["python"], source="test",
            raw_data={"key": "val"},
        )
        d = job.to_dict()
        assert d["salary_currency"] == "EUR"
        assert d["is_remote"] is True
        assert d["raw_data"] == {"key": "val"}


# ─── HackerNews Scraper ──────────────────────────────────────────────────────


class TestHackerNewsScraper:
    """Tests for HackerNewsScraper."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper
        return HackerNewsScraper()

    def test_source_name(self, scraper):
        assert scraper.source_name == "hackernews"

    def test_rate_limit(self, scraper):
        assert scraper.rate_limit == 30

    def test_extract_company(self, scraper):
        company = scraper._extract_company("TechCorp | Dev | Remote")
        assert company is not None
        assert "TechCorp" in company

    def test_extract_tags(self, scraper):
        tags = scraper._extract_tags("Looking for a senior Python developer with remote work")
        assert "python" in tags
        assert "senior" in tags
        assert "remote" in tags

    def test_extract_tags_empty(self, scraper):
        tags = scraper._extract_tags("Looking for a general role")
        assert tags == []

    def test_extract_title_pipe(self, scraper):
        title = scraper._extract_title("TechCorp | Senior Python Developer | Remote")
        assert title is not None
        assert len(title) > 5

    def test_extract_title_hyphen(self, scraper):
        title = scraper._extract_title("TechCorp - Python Developer - NYC")
        assert title is not None

    def test_extract_title_no_match(self, scraper):
        assert scraper._extract_title("short") is None

    def test_parse_comment_valid(self, scraper):
        comment = {
            "id": 123,
            "text": "TechCorp | Python Developer | Remote<p>Build APIs with Python",
            "time": 1700000000,
        }
        job = scraper._parse_comment(comment, "python")
        assert job is not None
        assert job.title is not None
        assert job.source == "hackernews"

    def test_parse_comment_no_text(self, scraper):
        assert scraper._parse_comment({"id": 1}, "python") is None

    def test_parse_comment_no_match(self, scraper):
        comment = {
            "id": 123,
            "text": "TechCorp | Java Developer | Remote<p>Build Java apps",
            "time": 1700000000,
        }
        assert scraper._parse_comment(comment, "python") is None

    @pytest.mark.asyncio
    async def test_get_latest_hiring_thread_found(self, scraper):
        mock_response = MagicMock()
        mock_response.json.return_value = [1, 2, 3]

        story_response = MagicMock()
        story_response.json.return_value = {"title": "Ask HN: Who is hiring?", "id": 2}

        scraper._get = AsyncMock(side_effect=[mock_response, story_response])

        result = await scraper._get_latest_hiring_thread()
        assert result == "1"

    @pytest.mark.asyncio
    async def test_get_latest_hiring_thread_not_found(self, scraper):
        mock_response = MagicMock()
        mock_response.json.return_value = [1]
        story_response = MagicMock()
        story_response.json.return_value = {"title": "Other thread"}

        scraper._get = AsyncMock(side_effect=[mock_response, story_response])

        result = await scraper._get_latest_hiring_thread()
        assert result is None


# ─── LinkedIn Scraper ───────────────────────────────────────────────────────


class TestLinkedInScraper:
    """Tests for LinkedInScraper."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.linkedin import LinkedInScraper
        return LinkedInScraper()

    def test_source_name(self, scraper):
        assert scraper.source_name == "linkedin"

    def test_rate_limit(self, scraper):
        assert scraper.rate_limit == 10

    def test_extract_tags(self, scraper):
        tags = scraper._extract_tags("Python Developer Remote", "React and AWS experience")
        assert "python" in tags
        assert "react" in tags
        assert "aws" in tags
        assert "remote" in tags

    def test_extract_tags_empty(self, scraper):
        tags = scraper._extract_tags("General role", None)
        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_success(self, scraper):
        html = """
        <ul>
            <li class="result-card">
                <h3 class="result-card__title">Python Developer</h3>
                <h4 class="result-card__company-name">TechCorp</h4>
                <a class="result-card__full-card-link" href="https://linkedin.com/jobs/123">Link</a>
                <span class="job-result__location">Remote</span>
                <time class="result-card__listed-date" datetime="2026-01-15">Jan 15</time>
                <p class="result-card__snippet">Build APIs</p>
            </li>
        </ul>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        scraper._get = AsyncMock(return_value=mock_response)

        jobs = await scraper.fetch("python", limit=5)
        assert len(jobs) == 1
        assert jobs[0].title == "Python Developer"

    @pytest.mark.asyncio
    async def test_fetch_error(self, scraper):
        scraper._get = AsyncMock(side_effect=Exception("Error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── Indeed Scraper ──────────────────────────────────────────────────────────


class TestIndeedScraper:
    """Tests for IndeedScraper."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.indeed import IndeedScraper
        return IndeedScraper()

    def test_source_name(self, scraper):
        assert scraper.source_name == "indeed"

    def test_rate_limit(self, scraper):
        assert scraper.rate_limit == 15

    def test_parse_salary_range(self, scraper):
        min_s, max_s = scraper._parse_salary("$80,000 - $120,000 per year")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_single(self, scraper):
        min_s, max_s = scraper._parse_salary("$100,000 per year")
        assert min_s == 100000
        assert max_s == 100000

    def test_parse_salary_no_match(self, scraper):
        min_s, max_s = scraper._parse_salary("Competitive salary")
        assert min_s is None
        assert max_s is None

    def test_extract_tags(self, scraper):
        tags = scraper._extract_tags(
            "Senior Python Developer Remote", "Docker and AWS required"
        )
        assert "python" in tags
        assert "senior" in tags
        assert "remote" in tags
        assert "docker" in tags
        assert "aws" in tags

    def test_extract_tags_empty(self, scraper):
        tags = scraper._extract_tags("General role", None)
        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_error(self, scraper):
        scraper._get = AsyncMock(side_effect=Exception("Error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── Glassdoor Scraper ───────────────────────────────────────────────────────


class TestGlassdoorScraper:
    """Tests for GlassdoorScraper."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.glassdoor import GlassdoorScraper
        return GlassdoorScraper()

    def test_source_name(self, scraper):
        assert scraper.source_name == "glassdoor"

    def test_rate_limit(self, scraper):
        assert scraper.rate_limit == 10

    def test_parse_salary_k_format(self, scraper):
        min_s, max_s = scraper._parse_salary("$80K - $120K")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_comma_format(self, scraper):
        min_s, max_s = scraper._parse_salary("$80,000 - $120,000")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_single_k(self, scraper):
        min_s, max_s = scraper._parse_salary("$100K")
        assert min_s == 100000
        assert max_s == 100000

    def test_parse_salary_no_match(self, scraper):
        min_s, max_s = scraper._parse_salary("Competitive")
        assert min_s is None
        assert max_s is None

    def test_extract_tags(self, scraper):
        tags = scraper._extract_tags(
            "Python Developer", "Machine learning experience"
        )
        assert "python" in tags
        assert "ml" in tags

    def test_extract_tags_empty(self, scraper):
        tags = scraper._extract_tags("General role", None)
        assert tags == []

    @pytest.mark.asyncio
    async def test_fetch_error(self, scraper):
        scraper._get = AsyncMock(side_effect=Exception("Error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── RemoteOK Scraper ────────────────────────────────────────────────────────


class TestRemoteOKScraper:
    """Tests for RemoteOKScraper."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper
        return RemoteOKScraper()

    def test_source_name(self, scraper):
        assert scraper.source_name == "remote_ok"

    def test_rate_limit(self, scraper):
        assert scraper.rate_limit == 30

    def test_parse_salary_range(self, scraper):
        min_s, max_s = scraper._parse_salary("$80,000 - $120,000")
        assert min_s == 80000
        assert max_s == 120000

    def test_parse_salary_single(self, scraper):
        min_s, max_s = scraper._parse_salary("$100,000")
        assert min_s == 100000
        assert max_s == 100000

    def test_parse_salary_none(self, scraper):
        min_s, max_s = scraper._parse_salary("Competitive")
        assert min_s is None
        assert max_s is None

    def test_parse_salary_empty(self, scraper):
        min_s, max_s = scraper._parse_salary("")
        assert min_s is None
        assert max_s is None

    def test_parse_date_valid(self, scraper):
        result = scraper._parse_date(1700000000)
        assert result is not None

    def test_parse_date_none(self, scraper):
        assert scraper._parse_date(None) is None

    def test_parse_job_matches_query(self, scraper):
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

    def test_parse_job_no_match(self, scraper):
        item = {
            "position": "Java Developer",
            "company": "TechCorp",
            "description": "Build Java apps",
        }
        job = scraper._parse_job(item, "python")
        assert job is None

    @pytest.mark.asyncio
    async def test_fetch_success(self, scraper):
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
    async def test_fetch_error(self, scraper):
        scraper._get = AsyncMock(side_effect=Exception("Network error"))
        jobs = await scraper.fetch("python")
        assert jobs == []


# ─── RSS Feed Scraper ────────────────────────────────────────────────────────


class TestRSSFeedScraper:
    """Tests for RSSFeedScraper."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        return RSSFeedScraper()

    def test_source_name(self, scraper):
        assert scraper.source_name == "rss_feed"

    def test_rate_limit(self, scraper):
        assert scraper.rate_limit == 60

    def test_custom_feeds(self):
        from interntrack.scrapers.rss_feeds import RSSFeedScraper
        feeds = {"custom": "https://example.com/rss"}
        scraper = RSSFeedScraper(feeds=feeds)
        assert scraper.feeds == feeds

    def test_extract_company_hiring(self, scraper):
        assert scraper._extract_company_from_title("TechCorp is hiring") == "TechCorp"

    def test_extract_company_brackets(self, scraper):
        assert scraper._extract_company_from_title("[Google] Python Dev") == "Google"

    def test_extract_company_unknown(self, scraper):
        assert scraper._extract_company_from_title("Random Title") == "Unknown"

    def test_extract_tags(self, scraper):
        tags = scraper._extract_tags("Python and React developer needed")
        assert "python" in tags
        assert "react" in tags

    def test_extract_tags_none(self, scraper):
        tags = scraper._extract_tags("General position")
        assert tags == []

    def test_parse_entry_matches_query(self, scraper):
        entry = {
            "title": "Python Developer at TechCorp",
            "link": "https://example.com",
            "summary": "Build APIs with Python",
        }
        job = scraper._parse_entry(entry, "python", "rss_feed")
        assert job is not None
        assert "Python" in job.title

    def test_parse_entry_no_match(self, scraper):
        entry = {
            "title": "Java Developer",
            "link": "https://example.com",
            "summary": "Build Java apps",
        }
        job = scraper._parse_entry(entry, "python", "rss_feed")
        assert job is None

    def test_parse_entry_with_date(self, scraper):
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
    async def test_fetch_feed_success(self, scraper):
        mock_response = MagicMock()
        mock_response.text = "<rss><channel></channel></rss>"
        scraper._get = AsyncMock(return_value=mock_response)

        with patch("interntrack.scrapers.rss_feeds.feedparser") as mock_feed:
            mock_feed.parse.return_value.entries = []
            jobs = await scraper._fetch_feed(
                "https://example.com/rss", "python", "test"
            )

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
        scraper = CustomRSSFeedScraper(
            ["https://a.com/rss", "https://b.com/rss"]
        )
        assert "custom_0" in scraper.feeds
        assert "custom_1" in scraper.feeds
        assert scraper.feeds["custom_0"] == "https://a.com/rss"
