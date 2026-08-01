"""
Unit tests for scraper implementations.
"""


import pytest

from interntrack.scrapers.hackernews import HackerNewsScraper
from interntrack.scrapers.remoteok import RemoteOKScraper
from interntrack.scrapers.rss_feeds import RSSFeedScraper


class TestHackerNewsScraper:
    """Tests for HackerNewsScraper."""

    @pytest.fixture
    def scraper(self):
        """Create HackerNewsScraper instance."""
        return HackerNewsScraper()

    def test_source_name(self, scraper):
        """Test source_name property."""
        assert scraper.source_name == "hackernews"

    def test_rate_limit(self, scraper):
        """Test rate_limit property."""
        assert scraper.rate_limit == 30

    def test_extract_company_from_title(self, scraper):
        """Test extracting company from title."""
        title = "TechCorp | Python Developer | Remote"
        result = scraper._extract_company(title)
        assert result is not None

    def test_extract_tags(self, scraper):
        """Test extracting tags from text."""
        text = "Looking for a Python developer with React experience"
        tags = scraper._extract_tags(text)
        assert "python" in tags
        assert "react" in tags


class TestRemoteOKScraper:
    """Tests for RemoteOKScraper."""

    @pytest.fixture
    def scraper(self):
        """Create RemoteOKScraper instance."""
        return RemoteOKScraper()

    def test_source_name(self, scraper):
        """Test source_name property."""
        assert scraper.source_name == "remote_ok"

    def test_rate_limit(self, scraper):
        """Test rate_limit property."""
        assert scraper.rate_limit == 30

    def test_parse_salary(self, scraper):
        """Test salary parsing."""
        salary_min, salary_max = scraper._parse_salary("$80,000 - $120,000")
        assert salary_min == 80000
        assert salary_max == 120000

    def test_parse_salary_no_match(self, scraper):
        """Test salary parsing with no numbers."""
        salary_min, salary_max = scraper._parse_salary("Competitive")
        assert salary_min is None
        assert salary_max is None


class TestRSSFeedScraper:
    """Tests for RSSFeedScraper."""

    @pytest.fixture
    def scraper(self):
        """Create RSSFeedScraper instance."""
        return RSSFeedScraper()

    def test_source_name(self, scraper):
        """Test source_name property."""
        assert scraper.source_name == "rss_feed"

    def test_rate_limit(self, scraper):
        """Test rate_limit property."""
        assert scraper.rate_limit == 60

    def test_extract_company_from_title(self, scraper):
        """Test extracting company from title."""
        title = "TechCorp is hiring Python developers"
        result = scraper._extract_company_from_title(title)
        assert result == "TechCorp"

    def test_extract_tags(self, scraper):
        """Test extracting tags from text."""
        text = "We need a Python developer with Docker experience"
        tags = scraper._extract_tags(text)
        assert "python" in tags
        assert "docker" in tags
