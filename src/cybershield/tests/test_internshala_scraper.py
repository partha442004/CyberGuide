"""
Unit tests for the Internshala scraper.

Covers search URL building, job data parsing (location, stipend,
internship defaults, skills, remote), and the scrape loop against mocked
fetch responses.
"""

import pytest

from cybershield.scrapers.india.internshala import InternshalaScraper


class TestInternshalaScraper:
    def setup_method(self):
        self.scraper = InternshalaScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "internshala"
        assert self.scraper.config.rate_limit == 0.5

    def test_build_search_url(self):
        url = self.scraper._build_search_url("cyber security", page=2)
        assert "/jobs/search" in url
        assert "searchTerm=cyber%20security" in url or "searchTerm=cyber+security" in url
        assert "page=2" in url

    def test_parse_full_job(self):
        job_data = {
            "title": "  Security Intern  ",
            "company_name": "  CyberCorp  ",
            "id": 77,
            "url": "security-intern-cybercorp",
            "location": "Pune, India",
            "stipend": {"salary": 15000},
            "skills": ["networking", "linux"],
            "remote": True,
            "duration": "6 months",
            "posted_date": "2024-02-01",
            "description": "Assist with penetration testing",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.title == "Security Intern"
        assert job.company_name == "CyberCorp"
        assert job.source == "internshala"
        assert job.source_id == "77"
        assert "internshala.com/jobs/" in (job.url or "")
        assert job.location == "Pune, India"
        assert job.country == "India"
        assert job.city == "Pune"
        assert job.salary_min == 15000
        assert job.salary_max == 15000
        assert job.salary_currency == "INR"
        assert job.experience_level == "intern"
        assert job.job_type == "internship"
        assert job.is_remote is True
        assert job.is_onsite is False
        assert job.raw_data["duration"] == "6 months"
        assert job.posting_date is not None

    def test_parse_onsite_job(self):
        job_data = {
            "title": "Intern",
            "company_name": "Acme",
            "id": 2,
            "url": "x",
            "location": "Mumbai",
            "skills": [],
            "remote": False,
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.is_remote is False
        assert job.is_onsite is True
        assert job.city == "Mumbai"

    def test_parse_skills_as_string(self):
        job_data = {
            "title": "Intern",
            "company_name": "Acme",
            "id": 3,
            "url": "x",
            "location": "",
            "skills": "Python, Bash",
        }
        job = self.scraper._parse_job_data(job_data)
        assert "Python" in job.required_skills
        assert "Bash" in job.required_skills

    def test_parse_no_stipend(self):
        job_data = {
            "title": "Intern",
            "company_name": "Acme",
            "id": 4,
            "url": "x",
            "location": "",
            "stipend": {},
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.salary_min is None

    def test_parse_description_skills_merged(self):
        job_data = {
            "title": "Intern",
            "company_name": "Acme",
            "id": 5,
            "url": "x",
            "location": "",
            "skills": [],
            "description": "Work with Python and AWS cloud security",
        }
        job = self.scraper._parse_job_data(job_data)
        names = [s.lower() for s in job.required_skills]
        assert "python" in names
        assert "aws" in names


class TestInternshalaScrape:
    @pytest.mark.asyncio
    async def test_scrape_returns_jobs(self, monkeypatch):
        scraper = InternshalaScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobs": [
                        {
                            "title": "Security Intern",
                            "company_name": "Acme",
                            "id": 100,
                            "url": "job-100",
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
    async def test_scrape_empty_breaks(self, monkeypatch):
        scraper = InternshalaScraper()

        class FakeResponse:
            def json(self):
                return {"jobs": []}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=3)
        assert jobs == []

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = InternshalaScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert jobs == []

    @pytest.mark.asyncio
    async def test_scrape_deduplicates(self, monkeypatch):
        scraper = InternshalaScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobs": [
                        {
                            "title": "Same Intern",
                            "company_name": "Acme",
                            "id": 55,
                            "url": "job-55",
                        }
                    ]
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["a", "b"], max_pages=1)
        assert len(jobs) == 1
