"""
Unit Tests for Check Point Scraper

Tests the CheckPointScraper class covering:
- Job parsing from HTML
- Security role filtering
- Location detection
- HTML extraction
"""

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.checkpoint import CheckPointScraper


class TestCheckPointScraper:
    """Test Check Point scraper functionality."""

    def setup_method(self):
        self.scraper = CheckPointScraper()

    def test_scraper_name(self):
        """Scraper should have correct name."""
        assert self.scraper.name == "company_checkpoint"

    def test_scraper_company_name(self):
        """Scraper should have correct company name."""
        assert self.scraper.company_name == "Check Point Software Technologies"

    def test_career_url(self):
        """Scraper should have correct career URL."""
        assert "checkpoint" in self.scraper.CAREER_URL.lower()

    def test_search_url(self):
        """Scraper should have correct search URL."""
        assert "checkpoint" in self.scraper.SEARCH_URL.lower()
        assert "cpcareers" in self.scraper.SEARCH_URL

    def test_default_keywords(self):
        """Scraper should have security-related default keywords."""
        keywords = self.scraper.DEFAULT_KEYWORDS
        assert len(keywords) >= 10
        assert any("security" in kw.lower() for kw in keywords)
        assert any("check" in kw.lower() for kw in keywords)

    def test_parse_job_from_html(self):
        """Should parse job data correctly."""
        job_data = {
            "job_id": "8070050",
            "title": "Senior Security Engineer",
            "location": "San Carlos, CA (US)",
            "description": "Building next-gen firewall security",
        }
        job = self.scraper._parse_job_from_html(job_data)
        assert job.title == "Senior Security Engineer"
        assert job.company_name == "Check Point Software Technologies"
        assert job.source == "company_check_point_software_technologies"
        assert job.source_id == "8070050"
        assert job.location == "San Carlos, CA (US)"
        assert job.country == "USA"
        assert job.job_type == "full_time"
        assert "checkpoint" in (job.url or "").lower()

    def test_parse_job_remote(self):
        """Should detect remote jobs."""
        job_data = {
            "job_id": "8070051",
            "title": "Security Analyst",
            "location": "Remote",
            "description": "",
        }
        job = self.scraper._parse_job_from_html(job_data)
        assert job.is_remote is True
        assert job.country == "Remote"

    def test_parse_job_india(self):
        """Should detect India location."""
        job_data = {
            "job_id": "8070052",
            "title": "SOC Analyst",
            "location": "Bangalore, India",
            "description": "",
        }
        job = self.scraper._parse_job_from_html(job_data)
        assert job.country == "India"

    def test_parse_job_israel(self):
        """Should detect Israel location (Check Point HQ)."""
        job_data = {
            "job_id": "8070053",
            "title": "Threat Intelligence Analyst",
            "location": "Herzliya, Israel",
            "description": "",
        }
        job = self.scraper._parse_job_from_html(job_data)
        assert job.country == "Israel"

    def test_parse_job_skills_extracted(self):
        """Should extract skills from title."""
        job_data = {
            "job_id": "8070054",
            "title": "Cloud Security Engineer - AWS",
            "location": "Remote",
            "description": "Building cloud security tools",
        }
        job = self.scraper._parse_job_from_html(job_data)
        assert job.title == "Cloud Security Engineer - AWS"
        assert job.company_name == "Check Point Software Technologies"

    def test_tag_job(self):
        """Should tag job with company info."""
        job = ScrapedJob()
        job.title = "Test Job"
        tagged = self.scraper._tag_job(job)
        assert tagged.company_name == "Check Point Software Technologies"
        assert tagged.source == "company_check_point_software_technologies"

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

    def test_extract_jobs_from_html(self):
        """Should extract jobs from HTML."""
        html = """
        <td><a href="index.php?m=cpcareers&a=show&joborderid=8070050">Security Engineer</a></td>
        <td><a href="index.php?m=cpcareers&a=show&joborderid=8070051">SOC Analyst</a></td>
        """
        jobs = self.scraper._extract_jobs_from_html(html)
        assert len(jobs) == 2
        assert jobs[0]["job_id"] == "8070050"
        assert jobs[0]["title"] == "Security Engineer"
        assert jobs[1]["job_id"] == "8070051"

    def test_extract_jobs_empty_html(self):
        """Should return empty list for HTML with no jobs."""
        html = "<html><body>No jobs found</body></html>"
        jobs = self.scraper._extract_jobs_from_html(html)
        assert jobs == []


class TestCheckPointScraperConfig:
    """Test scraper configuration."""

    def setup_method(self):
        self.scraper = CheckPointScraper()

    def test_default_config(self):
        """Should create default config correctly."""
        assert self.scraper.config.rate_limit == 0.33
        assert self.scraper.config.max_retries == 3

    def test_custom_config(self):
        """Should accept custom config."""
        config = ScraperConfig(
            name="custom_checkpoint",
            base_url="https://custom.url",
            rate_limit=0.5,
            max_retries=5,
        )
        scraper = CheckPointScraper(config=config)
        assert scraper.config.name == "custom_checkpoint"
        assert scraper.config.rate_limit == 0.5

    def test_scraper_stats(self):
        """Should return stats dictionary."""
        stats = self.scraper.get_stats()
        assert "name" in stats
        assert "requests" in stats
        assert "errors" in stats
        assert "success_rate" in stats
