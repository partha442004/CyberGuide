"""
Unit tests for the Freshersworld scraper.

Covers search URL building, job data parsing (location, salary in LPA,
fresher defaults, skills), and the scrape loop against mocked responses.
"""

import pytest

from cybershield.scrapers.india.freshersworld import FreshersworldScraper


class TestFreshersworldScraper:
    def setup_method(self):
        self.scraper = FreshersworldScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "freshersworld"
        assert self.scraper.config.rate_limit == 0.5

    def test_build_search_url(self):
        url = self.scraper._build_search_url("cyber security", page=2)
        assert "freshersworld.com/jobs/search" in url
        assert "pageNo=2" in url

    def test_parse_full_job(self):
        job_data = {
            "jobTitle": "  Cyber Security Analyst  ",
            "companyName": "  SecureCo  ",
            "jobUrl": "https://freshersworld.com/job/9",
            "jobId": "fw-1",
            "location": "Chennai, Tamil Nadu",
            "salary": "₹4 - ₹8 LPA",
            "skills": ["networking", "linux"],
            "postedDate": "2024-01-20",
            "description": "Assess network security with Nmap",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.title == "Cyber Security Analyst"
        assert job.company_name == "SecureCo"
        assert job.source == "freshersworld"
        assert job.source_id == "fw-1"
        assert job.location == "Chennai, Tamil Nadu"
        assert job.country == "India"
        assert job.city == "Chennai"
        assert job.salary_min == 400000
        assert job.salary_max == 800000
        assert job.salary_currency == "INR"
        assert job.experience_level == "fresher"
        assert job.job_type == "full_time"
        assert "networking" in job.required_skills
        assert job.posting_date is not None

    def test_parse_single_salary(self):
        job_data = {
            "jobTitle": "Analyst",
            "companyName": "Acme",
            "jobId": "fw-2",
            "location": "",
            "salary": "₹5 LPA",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.salary_min == 500000
        assert job.salary_max == 500000

    def test_parse_not_disclosed_salary(self):
        job_data = {
            "jobTitle": "Analyst",
            "companyName": "Acme",
            "jobId": "fw-3",
            "location": "",
            "salary": "Not Disclosed",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.salary_min is None

    def test_parse_skills_as_string(self):
        job_data = {
            "jobTitle": "Analyst",
            "companyName": "Acme",
            "jobId": "fw-4",
            "location": "",
            "skills": "Python, SIEM",
        }
        job = self.scraper._parse_job_data(job_data)
        assert "Python" in job.required_skills
        assert "SIEM" in job.required_skills

    def test_parse_no_id_falls_back(self):
        job_data = {
            "jobTitle": "Analyst",
            "companyName": "Acme",
            "id": "fallback-id",
            "location": "",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.source_id == "fallback-id"

    def test_parse_description_skills(self):
        job_data = {
            "jobTitle": "Analyst",
            "companyName": "Acme",
            "jobId": "fw-5",
            "location": "",
            "description": "Work with Splunk and Wireshark",
        }
        job = self.scraper._parse_job_data(job_data)
        names = [s.lower() for s in job.required_skills]
        assert "splunk" in names
        assert "wireshark" in names


class TestFreshersworldScrape:
    @pytest.mark.asyncio
    async def test_scrape_returns_jobs(self, monkeypatch):
        scraper = FreshersworldScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobs": [
                        {
                            "jobTitle": "Security Analyst",
                            "companyName": "Acme",
                            "jobId": "100",
                        }
                    ]
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "100"

    @pytest.mark.asyncio
    async def test_scrape_results_key_fallback(self, monkeypatch):
        scraper = FreshersworldScraper()

        class FakeResponse:
            def json(self):
                return {
                    "results": [
                        {
                            "jobTitle": "Security Analyst",
                            "companyName": "Acme",
                            "jobId": "200",
                        }
                    ]
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_scrape_empty_breaks(self, monkeypatch):
        scraper = FreshersworldScraper()

        class FakeResponse:
            def json(self):
                return {"jobs": []}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=3) == []

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = FreshersworldScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=1) == []
