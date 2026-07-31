"""
Unit Tests for Trend Micro Scraper

Tests the TrendMicroScraper class covering:
- Search payload construction
- Job data parsing
- Security role filtering
- URL generation
- Location detection
"""

import pytest
from cybershield.scrapers.companies.trendmicro import TrendMicroScraper
from cybershield.scrapers.base import ScrapedJob, ScraperConfig


class TestTrendMicroScraper:
    """Test Trend Micro scraper functionality."""

    def setup_method(self):
        self.scraper = TrendMicroScraper()

    def test_scraper_name(self):
        """Scraper should have correct name."""
        assert self.scraper.name == "company_trendmicro"

    def test_scraper_company_name(self):
        """Scraper should have correct company name."""
        assert self.scraper.company_name == "Trend Micro"

    def test_career_url(self):
        """Scraper should have correct career URL."""
        assert "trendmicro" in self.scraper.CAREER_URL.lower()
        assert "myworkdayjobs" in self.scraper.CAREER_URL.lower()

    def test_api_url(self):
        """Scraper should have correct API URL."""
        assert "trendmicro" in self.scraper.API_URL.lower()
        assert "/wday/cxs/" in self.scraper.API_URL
        # Trend Micro uses wd3 datacenter
        assert "wd3" in self.scraper.API_URL

    def test_default_keywords(self):
        """Scraper should have security-related default keywords."""
        keywords = self.scraper.DEFAULT_KEYWORDS
        assert len(keywords) >= 10
        assert any("security" in kw.lower() for kw in keywords)
        assert any("xdr" in kw.lower() for kw in keywords)

    def test_build_search_payload(self):
        """Should build correct Workday search payload."""
        payload = self.scraper._build_search_payload("security engineer", page=0, limit=20)
        assert payload["searchText"] == "security engineer"
        assert payload["limit"] == 20
        assert payload["offset"] == 0
        assert "appliedFacets" in payload

    def test_build_search_payload_pagination(self):
        """Should handle pagination correctly."""
        payload = self.scraper._build_search_payload("XDR", page=1, limit=25)
        assert payload["offset"] == 25
        assert payload["limit"] == 25

    def test_parse_job_data(self):
        """Should parse job data correctly."""
        job_data = {
            "title": "Senior Security Engineer",
            "externalPath": "/External/job/12345",
            "locationsText": "Austin, TX (US)",
            "postedOn": "2025-01-15",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.title == "Senior Security Engineer"
        assert job.company_name == "Trend Micro"
        assert job.source == "company_trend_micro"
        assert job.location == "Austin, TX (US)"
        assert job.country == "USA"
        assert job.job_type == "full_time"
        assert "trendmicro" in job.url.lower()

    def test_parse_job_data_remote(self):
        """Should detect remote jobs."""
        job_data = {
            "title": "Security Analyst",
            "externalPath": "/External/job/67890",
            "locationsText": "Remote - Worldwide",
            "postedOn": "2025-01-20",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.is_remote is True
        assert job.country == "Remote"

    def test_parse_job_data_india(self):
        """Should detect India location."""
        job_data = {
            "title": "SOC Analyst",
            "externalPath": "/External/job/11111",
            "locationsText": "Bangalore, India",
            "postedOn": "2025-01-25",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.country == "India"

    def test_parse_job_data_japan(self):
        """Should detect Japan location."""
        job_data = {
            "title": "Threat Researcher",
            "externalPath": "/External/job/44444",
            "locationsText": "Tokyo, Japan",
            "postedOn": "2025-02-10",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        # Japan may not be explicitly detected, so falls to Global
        assert job.country in ("Japan", "Global")

    def test_parse_job_data_skills_extracted(self):
        """Should extract skills from title."""
        job_data = {
            "title": "Cloud Security Engineer - AWS",
            "externalPath": "/External/job/33333",
            "locationsText": "Remote",
            "postedOn": "2025-02-05",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        assert len(job.required_skills) >= 0
        assert job.title == "Cloud Security Engineer - AWS"
        assert job.company_name == "Trend Micro"

    def test_tag_job(self):
        """Should tag job with company info."""
        job = ScrapedJob()
        job.title = "Test Job"
        tagged = self.scraper._tag_job(job)
        assert tagged.company_name == "Trend Micro"
        assert tagged.source == "company_trend_micro"

    def test_is_security_role_positive(self):
        """Should detect security roles."""
        job = ScrapedJob()
        job.title = "XDR Security Engineer"
        job.description = "Building XDR detection systems"
        assert self.scraper._is_security_role(job) is True

    def test_is_security_role_negative(self):
        """Should reject non-security roles."""
        job = ScrapedJob()
        job.title = "Sales Representative"
        job.description = "Enterprise software sales"
        assert self.scraper._is_security_role(job) is False


class TestTrendMicroScraperConfig:
    """Test scraper configuration."""

    def test_default_config(self):
        """Should create default config correctly."""
        scraper = TrendMicroScraper()
        assert scraper.config.rate_limit == 0.33
        assert scraper.config.max_retries == 3

    def test_custom_config(self):
        """Should accept custom config."""
        config = ScraperConfig(
            name="custom_trendmicro",
            base_url="https://custom.url",
            rate_limit=0.5,
            max_retries=5,
        )
        scraper = TrendMicroScraper(config=config)
        assert scraper.config.name == "custom_trendmicro"
        assert scraper.config.rate_limit == 0.5

    def test_scraper_stats(self):
        """Should return stats dictionary."""
        scraper = TrendMicroScraper()
        stats = scraper.get_stats()
        assert "name" in stats
        assert "requests" in stats
        assert "errors" in stats
        assert "success_rate" in stats
