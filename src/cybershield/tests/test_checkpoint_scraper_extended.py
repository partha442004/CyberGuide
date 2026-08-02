"""
Extended tests for the Check Point scraper.

Covers the remaining country-detection branches, the URL fallback when a
job id is missing, location extraction from HTML, and the full scrape
loop against a mocked fetch.
"""

import pytest

from cybershield.scrapers.companies.checkpoint import CheckPointScraper


class TestCheckPointParseExtended:
    def setup_method(self):
        self.scraper = CheckPointScraper()

    def test_parse_job_no_job_id_uses_career_url(self):
        job = self.scraper._parse_job_from_html(
            {"title": "Security Engineer", "location": "Remote"}
        )
        assert job.url == self.scraper.CAREER_URL
        assert job.country == "Remote"

    def test_parse_job_country_branches(self):
        cases = {
            "Tel Aviv, Israel": "Israel",
            "Singapore": "Singapore",
            "Sydney, Australia": "Australia",
            "Toronto, Canada": "Canada",
            "Berlin, Germany": "Germany",
            "London, UK": "UK",
            "Dubai, UAE": "Global",
            "New York, NY, USA": "USA",
            "Bengaluru, India": "India",
        }
        for location, expected in cases.items():
            job = self.scraper._parse_job_from_html(
                {"title": "Analyst", "job_id": "x", "location": location}
            )
            assert job.country == expected, location

    def test_parse_job_no_location_defaults_remote(self):
        job = self.scraper._parse_job_from_html({"title": "Analyst", "job_id": "y"})
        assert job.country == "Remote"

    def test_parse_job_experience_level_mid(self):
        job = self.scraper._parse_job_from_html({"title": "Analyst", "job_id": "z", "location": ""})
        assert job.experience_level == "mid"
        assert job.job_type == "full_time"

    def test_extract_jobs_with_locations(self):
        html = """
        <tr>
          <td><a href="index.php?m=cpcareers&a=show&joborderid=101">Threat Analyst</a></td>
          <td class="location">Tel Aviv, Israel</td>
        </tr>
        <tr>
          <td><a href="index.php?m=cpcareers&a=show&joborderid=102">SOC Analyst</a></td>
          <td class="location">Bangalore, India</td>
        </tr>
        """
        jobs = self.scraper._extract_jobs_from_html(html)
        assert len(jobs) == 2
        assert jobs[0]["job_id"] == "101"
        assert jobs[0]["location"] == "Tel Aviv, Israel"
        assert jobs[1]["location"] == "Bangalore, India"

    def test_extract_jobs_missing_location(self):
        html = '<td><a href="index.php?m=cpcareers&a=show&joborderid=55">Engineer</a></td>'
        jobs = self.scraper._extract_jobs_from_html(html)
        assert len(jobs) == 1
        assert jobs[0]["location"] == ""


class TestCheckPointScrapeExtended:
    @pytest.mark.asyncio
    async def test_scrape_collects_security_jobs(self, monkeypatch):
        scraper = CheckPointScraper()

        async def fake_fetch_search(keyword, page=1):
            if page == 1:
                return (
                    '<a href="index.php?m=cpcareers&a=show&joborderid=1">'
                    "Security Engineer</a>"
                    '<a href="index.php?m=cpcareers&a=show&joborderid=2">'
                    "Marketing</a>"
                )
            return ""

        async def fake_wait():
            return None

        monkeypatch.setattr(scraper, "_fetch_search_page", fake_fetch_search)
        monkeypatch.setattr(scraper, "_rate_limit_wait", fake_wait)
        jobs = await scraper.scrape(keywords=["security"], max_pages=2)
        assert len(jobs) == 1
        assert jobs[0].source_id == "1"

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = CheckPointScraper()

        async def fake_fetch_search(keyword, page=1):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch_search_page", fake_fetch_search)
        assert await scraper.scrape(keywords=["security"], max_pages=1) == []
