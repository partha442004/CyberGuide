"""
Tests for the cybershield worldwide scrapers (HackerNews, RemoteOK, RSS).

Covers thread discovery, comment parsing (all branches), job-data parsing,
feed-entry parsing, and the async scrape loops.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.scrapers.worldwide.hackernews import HackerNewsScraper
from cybershield.scrapers.worldwide.remoteok import RemoteOKScraper
from cybershield.scrapers.worldwide.rss_feeds import RSSFeedScraper


class TestHackerNewsFindThreads:
    def setup_method(self):
        self.scraper = HackerNewsScraper()

    @pytest.mark.asyncio
    async def test_finds_threads(self):
        response = MagicMock()
        response.json.return_value = {"hits": [{"objectID": "1"}, {"objectID": "2"}, "not-a-dict"]}
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        threads = await self.scraper._find_hiring_threads(limit=5)
        assert len(threads) == 2
        await_args = self.scraper._fetch.await_args
        assert await_args is not None
        assert await_args.kwargs["params"]["tags"] == "story"


class TestHackerNewsGetComments:
    def setup_method(self):
        self.scraper = HackerNewsScraper()

    @pytest.mark.asyncio
    async def test_empty_story(self):
        response = MagicMock()
        response.json.return_value = None
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]
        assert await self.scraper._get_comment_items(123) == []

    @pytest.mark.asyncio
    async def test_no_kids(self):
        response = MagicMock()
        response.json.return_value = {"id": 123}
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]
        assert await self.scraper._get_comment_items(123) == []

    @pytest.mark.asyncio
    async def test_fetches_comments(self):
        story_resp = MagicMock()
        story_resp.json.return_value = {"id": 123, "kids": [1, 2]}
        comments_by_id = {
            1: {"id": 1, "type": "comment", "text": "first"},
            2: {"id": 2, "type": "comment", "text": "second"},
        }

        async def fake_fetch(url, **kwargs):
            if "item/123" in url:
                return story_resp
            item_id = int(url.rsplit("/", 1)[1].split(".")[0])
            resp = MagicMock()
            resp.json.return_value = comments_by_id.get(item_id)
            return resp

        self.scraper._fetch = fake_fetch  # type: ignore[assignment]
        items = await self.scraper._get_comment_items(123, max_comments=10)
        assert len(items) == 2
        assert {i["id"] for i in items} == {1, 2}

    @pytest.mark.asyncio
    async def test_skips_non_comments(self):
        story_resp = MagicMock()
        story_resp.json.return_value = {"id": 123, "kids": [1]}
        comment_resp = MagicMock()
        comment_resp.json.return_value = {"id": 1, "type": "story"}
        self.scraper._fetch = AsyncMock(return_value=story_resp)  # type: ignore[method-assign]

        async def fake_fetch(url, **kwargs):
            if "item/123" in url:
                return story_resp
            return comment_resp

        self.scraper._fetch = fake_fetch  # type: ignore[assignment]
        items = await self.scraper._get_comment_items(123)
        assert items == []


class TestHackerNewsParseComment:
    def setup_method(self):
        self.scraper = HackerNewsScraper()

    def test_short_text_returns_empty(self):
        assert self.scraper._parse_comment({"text": "hi"}) == []

    def test_non_security_returns_empty(self):
        comment = {"text": "<p>We are hiring a Ruby developer to build internal tooling.</p>" * 5}
        assert self.scraper._parse_comment(comment) == []

    def test_full_parse(self):
        text = (
            "<p>Acme Corp | Remote | Security Engineer</p>"
            "<p>We are looking for a security engineer with SIEM experience.</p>"
        )
        comment = {"id": 42, "text": text, "time": 1700000000}
        jobs = self.scraper._parse_comment(comment)
        assert len(jobs) == 1
        job = jobs[0]
        assert job.company_name == "Acme Corp"
        assert job.is_remote is True
        assert job.location == "Remote"
        assert job.country == "Remote"
        assert job.source == "hackernews"
        assert job.source_id == "42"
        assert job.url == "https://news.ycombinator.com/item?id=42"
        assert job.title
        assert "security engineer" in job.title.lower()
        assert job.job_type == "full_time"

    def test_pipe_location(self):
        text = "<p>Acme Corp | New York | Backend</p><p>security analyst needed</p>"
        jobs = self.scraper._parse_comment({"id": 5, "text": text, "time": 0})
        assert jobs
        assert jobs[0].location == "New York"

    def test_no_pipe_uses_first_line(self):
        text = "<p>Acme Security Inc</p><p>Looking for a SOC analyst</p>"
        jobs = self.scraper._parse_comment({"id": 6, "text": text, "time": 0})
        assert jobs
        assert jobs[0].company_name
        assert "Acme Security Inc" in jobs[0].company_name

    def test_title_fallback(self):
        text = "<p>Acme Corp</p><p>We are hiring a security role at acme corporation today.</p>"
        jobs = self.scraper._parse_comment({"id": 7, "text": text, "time": 0})
        assert jobs
        assert jobs[0].title
        assert "Security Role" in jobs[0].title


class TestHackerNewsScrape:
    def setup_method(self):
        self.scraper = HackerNewsScraper()

    @pytest.mark.asyncio
    async def test_scrape_flow(self):
        thread = {"objectID": "9", "title": "Who is hiring? (2026-08)"}
        comment = {
            "id": 99,
            "type": "comment",
            "text": (
                "<p>Acme Corp | Remote</p>"
                "<p>We are looking for a security engineer with SIEM skills.</p>"
            ),
            "time": 1700000000,
        }
        self.scraper._find_hiring_threads = AsyncMock(return_value=[thread])  # type: ignore[method-assign]
        self.scraper._get_comment_items = AsyncMock(return_value=[comment])  # type: ignore[method-assign]

        jobs = await self.scraper.scrape(max_threads=3)
        assert len(jobs) == 1
        assert jobs[0].source_id == "99"

    @pytest.mark.asyncio
    async def test_scrape_error(self):
        self.scraper._find_hiring_threads = AsyncMock(side_effect=Exception("boom"))  # type: ignore[method-assign]
        jobs = await self.scraper.scrape()
        assert jobs == []


class TestRemoteOK:
    def setup_method(self):
        self.scraper = RemoteOKScraper()

    def test_parse_job_data_full(self):
        job = self.scraper._parse_job_data(
            {
                "id": "123",
                "position": "Security Engineer",
                "company": "Acme",
                "url": "https://remoteok.com/123",
                "tags": ["security", "python"],
                "salary_min": "90000",
                "salary_max": "120000",
                "description": "Need a security engineer",
                "date": "2026-08-01",
            }
        )
        assert job.title == "Security Engineer"
        assert job.company_name == "Acme"
        assert job.is_remote is True
        assert job.country == "Remote"
        assert job.source_id == "123"
        assert job.salary_min == 90000.0
        assert job.salary_max == 120000.0
        assert job.salary_currency == "USD"
        assert "security" in job.required_skills
        assert job.job_type == "full_time"

    def test_parse_job_data_minimal(self):
        job = self.scraper._parse_job_data({"id": "1", "position": "Role", "company": "Co"})
        assert job.title == "Role"
        assert job.salary_min is None

    def test_parse_job_data_no_description(self):
        job = self.scraper._parse_job_data(
            {"id": "2", "position": "Role", "company": "Co", "tags": ["devsecops"]}
        )
        assert "devsecops" in job.required_skills

    @pytest.mark.asyncio
    async def test_scrape_matches_keyword(self):
        response = MagicMock()
        response.json.return_value = [
            {"legal": "RemoteOK legal footer"},
            {"id": "10", "position": "Security Engineer", "company": "Acme", "tags": ["security"]},
            {"id": "11", "position": "UX Designer", "company": "Other", "tags": ["design"]},
        ]
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        jobs = await self.scraper.scrape(keywords=["security"])
        assert len(jobs) == 1
        assert jobs[0].source_id == "10"

    @pytest.mark.asyncio
    async def test_scrape_skips_metadata(self):
        response = MagicMock()
        response.json.return_value = [
            {"id": "20", "position": "SOC Analyst", "company": "Acme", "tags": ["soc"]}
        ]
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]
        jobs = await self.scraper.scrape(keywords=["soc"])
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_scrape_error(self):
        self.scraper._fetch = AsyncMock(side_effect=Exception("boom"))  # type: ignore[method-assign]
        assert await self.scraper.scrape() == []


class TestRSSFeed:
    def setup_method(self):
        self.scraper = RSSFeedScraper()

    def test_parse_feed_entry_full(self):
        entry = {
            "title": "Security Engineer - Acme",
            "link": "https://example.com/jobs/1",
            "id": "entry-1",
            "summary": "We need a security engineer with SIEM experience.",
            "published": "2026-08-01T10:00:00Z",
        }
        job = self.scraper._parse_feed_entry(entry, "TestFeed")
        assert job is not None
        assert job.title == "Security Engineer"
        assert job.company_name == "Acme"
        assert job.source == "rss_testfeed"
        assert job.source_id == "entry-1"
        assert job.is_remote is True
        assert job.country == "Remote"
        assert job.job_type == "full_time"

    def test_parse_feed_entry_no_security_keywords(self):
        entry = {
            "title": "Janitor",
            "link": "https://example.com/2",
            "summary": "Cleaning the office.",
        }
        assert self.scraper._parse_feed_entry(entry, "TestFeed") is None

    def test_parse_feed_entry_no_dash(self):
        entry = {
            "title": "Security Officer",
            "link": "https://example.com/3",
            "summary": "cyber security job",
        }
        job = self.scraper._parse_feed_entry(entry, "TestFeed")
        assert job is not None
        # company_name stays unset when the title has no " - " separator
        assert job.company_name in (None, "")

    def test_parse_feed_entry_error(self):
        self.scraper._normalize_url = MagicMock(side_effect=Exception("bad"))  # type: ignore[method-assign]
        entry = {"title": "Security", "link": "x", "summary": "security"}
        assert self.scraper._parse_feed_entry(entry, "TestFeed") is None

    @pytest.mark.asyncio
    async def test_scrape_with_explicit_feeds(self):
        feed = MagicMock()
        feed.entries = [
            {
                "title": "Security Engineer - Acme",
                "link": "https://example.com/jobs/1",
                "id": "entry-1",
                "summary": "security role",
            }
        ]
        response = MagicMock()
        response.text = "<rss></rss>"
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        with patch("cybershield.scrapers.worldwide.rss_feeds.parse_feed", return_value=feed):
            jobs = await self.scraper.scrape(
                feeds={"Custom": "https://example.com/feed"}, include_job_feeds=False
            )
        assert len(jobs) == 1
        assert jobs[0].source_id == "entry-1"

    @pytest.mark.asyncio
    async def test_scrape_dedupes(self):
        feed = MagicMock()
        feed.entries = [
            {
                "title": "Security - A",
                "link": "https://example.com/1",
                "id": "same",
                "summary": "security",
            },
            {
                "title": "Security - B",
                "link": "https://example.com/2",
                "id": "same",
                "summary": "cyber security",
            },
        ]
        response = MagicMock()
        response.text = "<rss></rss>"
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        with patch("cybershield.scrapers.worldwide.rss_feeds.parse_feed", return_value=feed):
            jobs = await self.scraper.scrape(
                feeds={"Custom": "https://example.com/feed"}, include_job_feeds=False
            )
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_scrape_error_continues(self):
        self.scraper._fetch = AsyncMock(side_effect=Exception("boom"))  # type: ignore[method-assign]
        jobs = await self.scraper.scrape(feeds={"A": "https://a"}, include_job_feeds=False)
        assert jobs == []
