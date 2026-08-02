"""
Unit tests for the company career-page scrapers.

Covers Amazon, Cisco, Google, and Microsoft scrapers: config defaults,
search URL building, job data parsing (locations, countries, remote
detection, skills), and the scrape loops against mocked fetch responses.
"""

import pytest

from cybershield.scrapers.companies.amazon import AmazonScraper
from cybershield.scrapers.companies.cisco import CiscoScraper
from cybershield.scrapers.companies.google import GoogleScraper
from cybershield.scrapers.companies.microsoft import MicrosoftScraper


class TestAmazonScraper:
    def setup_method(self):
        self.scraper = AmazonScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "company_amazon"
        assert self.scraper.company_name == "Amazon"
        assert self.scraper.config.rate_limit == 0.33

    def test_build_search_url(self):
        url = self.scraper._build_search_url("security engineer", page=2)
        assert "amazon.jobs/en/search.json" in url
        assert "base=security%20engineer" in url or "base=security+engineer" in url
        assert "p=2" in url

    def test_parse_job_usa(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Security Engineer",
                "job_id": "amz-1",
                "location": "Seattle, WA, United States",
                "description": "AWS cloud security",
            }
        )
        assert job.title == "Security Engineer"
        assert job.company_name == "Amazon"
        assert job.source == "company_amazon"
        assert job.source_id == "amz-1"
        assert job.country == "USA"
        assert "amazon.jobs/en/jobs/amz-1" in (job.url or "")
        assert job.job_type == "full_time"

    def test_parse_job_remote(self):
        job = self.scraper._parse_job_data(
            {"title": "Cloud Security", "job_id": "amz-2", "location": "Remote"}
        )
        assert job.is_remote is True
        assert job.country == "Remote"

    def test_parse_job_india(self):
        job = self.scraper._parse_job_data(
            {"title": "Security Analyst", "job_id": "amz-3", "location": "Hyderabad, India"}
        )
        assert job.country == "India"

    def test_parse_team_in_raw_data(self):
        job = self.scraper._parse_job_data(
            {"title": "Security", "job_id": "amz-4", "team": "AWS Shield"}
        )
        assert job.raw_data["team"] == "AWS Shield"

    @pytest.mark.asyncio
    async def test_scrape_filters_security_roles(self, monkeypatch):
        scraper = AmazonScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobs": [
                        {"title": "Security Engineer", "job_id": "1"},
                        {"title": "Marketing Manager", "job_id": "2"},
                    ]
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "1"

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = AmazonScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=1) == []


class TestCiscoScraper:
    def setup_method(self):
        self.scraper = CiscoScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "company_cisco"
        assert self.scraper.company_name == "Cisco"

    def test_build_search_url(self):
        url = self.scraper._build_search_url("security", page=1)
        assert "jobs.cisco.com/api/search" in url
        assert "keyword=security" in url

    def test_parse_job(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Security Engineer",
                "jobId": "cis-1",
                "locations": ["San Jose, California, USA"],
                "jobDescription": "Network security with Python",
                "tags": ["Security"],
                "datePosted": "2024-03-01",
                "department": "Security & Trust",
            }
        )
        assert job.title == "Security Engineer"
        assert job.source_id == "cis-1"
        assert "USA" in (job.country or "")
        assert "San Jose" in (job.location or "")
        assert "Security" in job.required_skills
        assert job.raw_data["department"] == "Security & Trust"
        assert job.posting_date is not None

    def test_parse_remote(self):
        job = self.scraper._parse_job_data(
            {"title": "Analyst", "jobId": "cis-2", "locations": ["Remote"]}
        )
        assert job.is_remote is True
        assert job.country == "Remote"

    @pytest.mark.asyncio
    async def test_scrape_nested_response(self, monkeypatch):
        scraper = CiscoScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobRequisitions": {
                        "requisitionList": [
                            {"title": "Threat Analyst", "jobId": "10"},
                            {"title": "Sales Rep", "jobId": "11"},
                        ]
                    }
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "10"


class TestGoogleScraper:
    def setup_method(self):
        self.scraper = GoogleScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "company_google"
        assert self.scraper.company_name == "Google"
        assert self.scraper.config.rate_limit == 0.25

    def test_build_search_url(self):
        url = self.scraper._build_search_url("security", page=2)
        assert "search/job" in url
        assert "start=20" in url

    def test_parse_job(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Security Engineer",
                "id": "g-1",
                "locations": ["Mountain View, CA, USA"],
                "description": "Cloud security with AWS and Python",
                "minimumQualifications": "5 years in security",
                "postedDate": "2024-01-10",
            }
        )
        assert job.title == "Security Engineer"
        assert job.source_id == "g-1"
        assert job.country == "USA"
        assert "google.com/about/careers" in (job.url or "")
        assert job.job_type == "full_time"
        assert "AWS" in job.required_skills or "aws" in [s.lower() for s in job.required_skills]

    def test_parse_india(self):
        job = self.scraper._parse_job_data(
            {"title": "Analyst", "id": "g-2", "locations": ["Bengaluru, India"]}
        )
        assert job.country == "India"

    @pytest.mark.asyncio
    async def test_scrape(self, monkeypatch):
        scraper = GoogleScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobs": [
                        {"title": "Security Analyst", "id": "g-10"},
                        {"title": "Recruiter", "id": "g-11"},
                    ]
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "g-10"


class TestMicrosoftScraper:
    def setup_method(self):
        self.scraper = MicrosoftScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "company_microsoft"
        assert self.scraper.company_name == "Microsoft"

    def test_build_search_url(self):
        url = self.scraper._build_search_url("security", page=2)
        assert "careers.microsoft.com/search/api" in url
        assert "pg=2" in url

    def test_parse_job(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Security Engineer",
                "jobId": "ms-1",
                "locations": ["Redmond, Washington, United States"],
                "description": "Azure security with Python",
                "tags": ["Security", "Azure"],
                "jobType": "Full-time",
                "postedDate": "2024-02-15",
            }
        )
        assert job.title == "Security Engineer"
        assert job.source_id == "ms-1"
        assert job.country == "USA"
        assert "careers.microsoft.com/global/en/job/ms-1" in (job.url or "")
        assert "Security" in job.required_skills
        assert job.posting_date is not None

    def test_parse_job_type_lowercased(self):
        job = self.scraper._parse_job_data(
            {"title": "Analyst", "jobId": "ms-2", "locations": [], "jobType": "Contract"}
        )
        assert job.job_type == "contract"

    @pytest.mark.asyncio
    async def test_scrape_deep_nested_response(self, monkeypatch):
        scraper = MicrosoftScraper()

        class FakeResponse:
            def json(self):
                return {
                    "operationResult": {
                        "result": {
                            "jobs": [
                                {"title": "Cloud Security", "jobId": "m-100"},
                                {"title": "UX Designer", "jobId": "m-101"},
                            ]
                        }
                    }
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "m-100"

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = MicrosoftScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=1) == []


class TestSecurityRoleFilter:
    def test_is_security_role(self):
        from cybershield.scrapers.base import ScrapedJob

        scraper = CiscoScraper()
        job = ScrapedJob()
        job.title = "Security Engineer"
        assert scraper._is_security_role(job) is True

    def test_is_not_security_role(self):
        from cybershield.scrapers.base import ScrapedJob

        scraper = CiscoScraper()
        job = ScrapedJob()
        job.title = "Marketing Manager"
        assert scraper._is_security_role(job) is False

    def test_description_keywords_count(self):
        from cybershield.scrapers.base import ScrapedJob

        scraper = CiscoScraper()
        job = ScrapedJob()
        job.title = "Analyst"
        job.description = "Handle incident response and malware analysis"
        assert scraper._is_security_role(job) is True
