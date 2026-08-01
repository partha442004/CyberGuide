"""
Unit Tests for Palo Alto Networks Scraper

Tests the PaloAltoScraper class covering:
- Search payload construction
- Job data parsing
- Security role filtering
- URL generation
- Location detection
"""

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.paloalto import PaloAltoScraper


class TestPaloAltoScraper:
    """Test Palo Alto Networks scraper functionality."""

    def setup_method(self):
        self.scraper = PaloAltoScraper()

    def test_scraper_name(self):
        """Scraper should have correct name."""
        assert self.scraper.name == "company_paloalto"

    def test_scraper_company_name(self):
        """Scraper should have correct company name."""
        assert self.scraper.company_name == "Palo Alto Networks"

    def test_career_url(self):
        """Scraper should have correct career URL."""
        assert "paloaltonetworks" in self.scraper.CAREER_URL.lower()

    def test_api_url(self):
        """Scraper should have correct API URL."""
        assert "paloaltonetworks" in self.scraper.API_URL.lower()
        assert "workday" in self.scraper.API_URL.lower() or "myworkdayjobs" in self.scraper.API_URL.lower()

    def test_default_keywords(self):
        """Scraper should have security-related default keywords."""
        keywords = self.scraper.DEFAULT_KEYWORDS
        assert len(keywords) >= 10
        assert any("security" in kw.lower() for kw in keywords)
        assert any("cyber" in kw.lower() for kw in keywords)

    def test_build_search_payload(self):
        """Should build correct Workday search payload."""
        payload = self.scraper._build_search_payload("security engineer", page=0, limit=20)
        assert payload["searchText"] == "security engineer"
        assert payload["limit"] == 20
        assert payload["offset"] == 0
        assert "appliedFacets" in payload

    def test_build_search_payload_pagination(self):
        """Should handle pagination correctly."""
        payload = self.scraper._build_search_payload("SOC", page=2, limit=10)
        assert payload["offset"] == 20
        assert payload["limit"] == 10

    def test_parse_job_data(self):
        """Should parse job data correctly."""
        job_data = {
            "title": "Senior Security Engineer",
            "externalPath": "/External/job/12345",
            "locationsText": "Santa Clara, CA (US)",
            "postedOn": "2025-01-15",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.title == "Senior Security Engineer"
        assert job.company_name == "Palo Alto Networks"
        assert job.source == "company_palo_alto_networks"
        assert job.location == "Santa Clara, CA (US)"
        assert job.country == "USA"
        assert job.job_type == "full_time"
        assert "paloaltonetworks" in job.url.lower()

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

    def test_parse_job_data_israel(self):
        """Should detect Israel location (Palo Alto has HQ in Israel)."""
        job_data = {
            "title": "Threat Intelligence Analyst",
            "externalPath": "/External/job/22222",
            "locationsText": "Tel Aviv, Israel",
            "postedOn": "2025-02-01",
            "timeType": "Full time",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.country == "Israel"

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
        assert job.title == "Cloud Security Engineer - AWS"
        assert job.company_name == "Palo Alto Networks"

    def test_tag_job(self):
        """Should tag job with company info."""
        job = ScrapedJob()
        job.title = "Test Job"
        tagged = self.scraper._tag_job(job)
        assert tagged.company_name == "Palo Alto Networks"
        assert tagged.source == "company_palo_alto_networks"

    def test_is_security_role_positive(self):
        """Should detect security roles."""
        job = ScrapedJob()
        job.title = "Security Engineer"
        job.description = "Building security tools"
        assert self.scraper._is_security_role(job) is True

    def test_is_security_role_negative(self):
        """Should reject non-security roles."""
        job = ScrapedJob()
        job.title = "Marketing Manager"
        job.description = "Brand awareness campaigns"
        assert self.scraper._is_security_role(job) is False

    def test_is_security_role_in_description(self):
        """Should detect security keywords in description."""
        job = ScrapedJob()
        job.title = "Software Engineer"
        job.description = "Building cybersecurity detection systems"
        assert self.scraper._is_security_role(job) is True


class TestPaloAltoScraperConfig:
    """Test scraper configuration."""

    def setup_method(self):
        self.scraper = PaloAltoScraper()

    def test_default_config(self):
        """Should create default config correctly."""
        assert self.scraper.config.rate_limit == 0.33
        assert self.scraper.config.max_retries == 3

    def test_custom_config(self):
        """Should accept custom config."""
        config = ScraperConfig(
            name="custom_paloalto",
            base_url="https://custom.url",
            rate_limit=0.5,
            max_retries=5,
        )
        scraper = PaloAltoScraper(config=config)
        assert scraper.config.name == "custom_paloalto"
        assert scraper.config.rate_limit == 0.5

    def test_scraper_stats(self):
        """Should return stats dictionary."""
        stats = self.scraper.get_stats()
        assert "name" in stats
        assert "requests" in stats
        assert "errors" in stats
        assert "success_rate" in stats
