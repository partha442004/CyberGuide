"""
Tests for Scrapers

Tests for base scraper and individual scrapers.
"""

import pytest

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig
from cybershield.scrapers.registry import ScraperRegistry


class TestBaseScraper:
    """Tests for BaseScraper."""

    def test_normalize_url(self):
        """Test URL normalization."""
        config = ScraperConfig(name="test", base_url="https://test.com")

        class TestScraper(BaseScraper):
            async def scrape(self, **kwargs):
                return []

        scraper = TestScraper(config)
        url = "https://example.com/job/123?utm_source=linkedin&ref=test"
        normalized = scraper._normalize_url(url)
        assert "utm_source" not in normalized
        assert "job/123" in normalized

    def test_generate_content_hash(self):
        """Test content hash generation."""
        config = ScraperConfig(name="test", base_url="https://test.com")

        class TestScraper(BaseScraper):
            async def scrape(self, **kwargs):
                return []

        scraper = TestScraper(config)
        hash1 = scraper._generate_content_hash("Title", "Company", "Location")
        hash2 = scraper._generate_content_hash("Title", "Company", "Location")
        assert hash1 == hash2

    def test_extract_skills(self):
        """Test skill extraction from text."""
        config = ScraperConfig(name="test", base_url="https://test.com")

        class TestScraper(BaseScraper):
            async def scrape(self, **kwargs):
                return []

        scraper = TestScraper(config)
        text = "Python and AWS experience required. SIEM knowledge preferred."
        skills = scraper._extract_skills(text)
        assert "Python" in skills
        assert "AWS" in skills

    def test_scraped_job_to_dict(self):
        """Test ScrapedJob serialization."""
        job = ScrapedJob()
        job.title = "Security Analyst"
        job.company_name = "Tech Corp"
        job.source = "linkedin"
        job.required_skills = ["Python", "SIEM"]

        data = job.to_dict()
        assert data["title"] == "Security Analyst"
        assert data["company_name"] == "Tech Corp"
        assert len(data["required_skills"]) == 2


class TestScraperRegistry:
    """Tests for ScraperRegistry."""

    def test_list_scrapers(self):
        """Test listing registered scrapers."""
        scrapers = ScraperRegistry.list_scrapers()
        assert "naukri" in scrapers
        assert "linkedin" in scrapers
        assert "indeed" in scrapers
        assert "remoteok" in scrapers

    def test_get_scrapers_by_region(self):
        """Test getting scrapers by region."""
        india = ScraperRegistry.get_scrapers_by_region("india")
        assert "naukri" in india
        assert "internshala" in india

        usa = ScraperRegistry.get_scrapers_by_region("usa")
        assert "linkedin" in usa
        assert "indeed" in usa

    def test_get_nonexistent_scraper(self):
        """Test getting non-existent scraper raises error."""
        with pytest.raises(ValueError):
            ScraperRegistry.get_scraper("nonexistent")


class TestScrapedJob:
    """Tests for ScrapedJob data class."""

    def test_create_job(self):
        """Test creating a ScrapedJob."""
        job = ScrapedJob()
        job.title = "Security Analyst"
        job.company_name = "Tech Corp"
        job.source = "linkedin"
        assert job.title == "Security Analyst"

    def test_to_dict(self):
        """Test dictionary conversion."""
        job = ScrapedJob()
        job.title = "Test"
        job.required_skills = ["Python"]
        data = job.to_dict()
        assert isinstance(data, dict)
        assert data["title"] == "Test"
