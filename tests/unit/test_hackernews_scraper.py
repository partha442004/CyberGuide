"""Unit tests for scrapers/hackernews.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestHackerNewsScraper:
    """Tests for HackerNewsScraper class."""

    def test_source_name(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        assert scraper.source_name == "hackernews"

    def test_rate_limit(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        assert scraper.rate_limit == 30

    def test_extract_title_with_pipe(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "TechCorp | Senior Python Developer | Remote"
        title = scraper._extract_title(text)
        assert title is not None
        # Title should be extracted from the pipe-separated parts
        assert len(title) > 0

    def test_extract_title_with_dash(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "TechCorp - Full Stack Engineer - NYC"
        title = scraper._extract_title(text)
        assert title is not None

    def test_extract_title_returns_none_for_short(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "Hi"
        title = scraper._extract_title(text)
        assert title is None

    def test_extract_company_with_pipe(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "TechCorp | Python Developer | Remote"
        company = scraper._extract_company(text)
        assert company is not None
        assert "TechCorp" in company

    def test_extract_company_returns_none(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = ""
        company = scraper._extract_company(text)
        assert company is None or company == ""

    def test_extract_tags_remote(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "We are a remote company looking for a developer"
        tags = scraper._extract_tags(text)
        assert "remote" in tags

    def test_extract_tags_python(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "Looking for a Python developer with experience"
        tags = scraper._extract_tags(text)
        assert "python" in tags

    def test_extract_tags_javascript(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "JavaScript and React experience required"
        tags = scraper._extract_tags(text)
        assert "javascript" in tags
        assert "react" in tags

    def test_extract_tags_senior(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "Senior position with leadership skills"
        tags = scraper._extract_tags(text)
        assert "senior" in tags

    def test_extract_tags_empty(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        text = "Looking for a good communicator"
        tags = scraper._extract_tags(text)
        assert len(tags) == 0

    def test_parse_comment_returns_none_for_empty(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        result = scraper._parse_comment({"text": ""}, "python")
        assert result is None

    def test_parse_comment_returns_none_for_no_match(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        comment = {
            "id": 123,
            "text": "TechCorp | Java Developer | NYC",
            "time": 1672531200,
        }
        result = scraper._parse_comment(comment, "python")
        assert result is None

    def test_parse_comment_returns_job_for_match(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        comment = {
            "id": 123,
            "text": "TechCorp | Python Developer | Remote | python, django, postgresql",
            "time": 1672531200,
        }
        result = scraper._parse_comment(comment, "python")
        assert result is not None
        assert result.title is not None
        assert result.source == "hackernews"
        assert "python" in result.tags

    def test_parse_comment_no_title(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()
        comment = {
            "id": 123,
            "text": "Hi",
            "time": 1672531200,
        }
        result = scraper._parse_comment(comment, "python")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_hiring_thread_found(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()

        mock_stories_response = MagicMock()
        mock_stories_response.json.return_value = [1, 2, 3]

        mock_story_response = MagicMock()
        mock_story_response.json.return_value = {
            "title": "Ask HN: Who is hiring? (July 2026)"
        }

        scraper._get = AsyncMock(return_value=mock_stories_response)

        # Make _get return different responses for different URLs
        async def mock_get(url, **kwargs):
            if "showstories" in url:
                return mock_stories_response
            return mock_story_response

        scraper._get = AsyncMock(side_effect=mock_get)

        result = await scraper._get_latest_hiring_thread()
        assert result == "1"

    @pytest.mark.asyncio
    async def test_get_latest_hiring_thread_not_found(self):
        from interntrack.scrapers.hackernews import HackerNewsScraper

        scraper = HackerNewsScraper()

        mock_stories_response = MagicMock()
        mock_stories_response.json.return_value = [1, 2, 3]

        mock_story_response = MagicMock()
        mock_story_response.json.return_value = {
            "title": "Ask HN: Best practices"
        }

        async def mock_get(url, **kwargs):
            if "showstories" in url:
                return mock_stories_response
            return mock_story_response

        scraper._get = AsyncMock(side_effect=mock_get)

        result = await scraper._get_latest_hiring_thread()
        assert result is None
