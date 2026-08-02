"""
Unit tests for the Naukri scraper.

Covers search URL building, job data parsing (location, salary,
experience, skills, job type, remote detection), and the scrape loop
against mocked fetch responses.
"""

import pytest

from cybershield.scrapers.india.naukri import NaukriScraper


class TestNaukriScraper:
    def setup_method(self):
        self.scraper = NaukriScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "naukri"
        assert self.scraper.config.rate_limit == 0.5
        assert self.scraper.config.max_retries == 3

    def test_build_search_url(self):
        url = self.scraper._build_search_url("cyber security", page=2)
        assert "jobapi/v3/search" in url
        assert "cyber%20security" in url or "cyber+security" in url
        assert "pageNum=2" in url
        assert "location=India" in url

    def test_parse_full_job(self):
        job_data = {
            "title": "  SOC Analyst  ",
            "companyName": "  Acme Corp  ",
            "jobUrl": "https://naukri.com/job/123",
            "jobId": "12345",
            "placeholders": [{"type": "location", "label": "Bangalore"}],
            "salaryDetails": {"label": "₹3,00,000 - ₹6,00,000 PA"},
            "experienceDetails": {"label": "3-5 yrs"},
            "tagsAndSkills": ["SIEM", "Python"],
            "jobType": "Full Time",
            "workMode": "Remote",
            "postedDate": "2024-01-15",
            "jobDescription": "Monitor security events with Splunk",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.title == "SOC Analyst"
        assert job.company_name == "Acme Corp"
        assert job.source == "naukri"
        assert job.source_id == "12345"
        assert job.location == "Bangalore"
        assert job.country == "India"
        assert job.city == "Bangalore"
        assert job.salary_min == 300000
        assert job.salary_max == 600000
        assert job.salary_currency == "INR"
        assert job.experience_level == "mid"
        assert job.job_type == "full_time"
        assert job.is_remote is True
        assert job.is_onsite is False
        assert "SIEM" in job.required_skills
        assert job.posting_date is not None

    def test_parse_hybrid_work_mode(self):
        job_data = {
            "title": "Security Engineer",
            "companyName": "Acme",
            "jobId": "1",
            "workMode": "Hybrid",
            "jobType": "Contract",
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.is_hybrid is True
        assert job.job_type == "contract"

    def test_parse_no_location(self):
        job_data = {"title": "Dev", "companyName": "Acme", "jobId": "2", "jobType": ""}
        job = self.scraper._parse_job_data(job_data)
        assert job.location is None
        assert job.country is None
        assert job.job_type == "full_time"

    def test_parse_skills_as_string(self):
        job_data = {
            "title": "Analyst",
            "companyName": "Acme",
            "jobId": "3",
            "jobType": "Internship",
            "tagsAndSkills": "Python, AWS, Splunk",
        }
        job = self.scraper._parse_job_data(job_data)
        assert "Python" in job.required_skills
        assert "AWS" in job.required_skills
        assert job.job_type == "internship"

    def test_parse_bad_salary_ignored(self):
        job_data = {
            "title": "Analyst",
            "companyName": "Acme",
            "jobId": "4",
            "salaryDetails": {"label": "Not disclosed"},
        }
        job = self.scraper._parse_job_data(job_data)
        assert job.salary_min is None

    def test_parse_description_skills_merged(self):
        job_data = {
            "title": "Security Analyst",
            "companyName": "Acme",
            "jobId": "5",
            "jobDescription": "Need Python and AWS experience for SIEM work",
        }
        job = self.scraper._parse_job_data(job_data)
        names = [s.lower() for s in job.required_skills]
        assert "python" in names
        assert "aws" in names
        # No duplicates
        assert len(job.required_skills) == len(set(job.required_skills))

    def test_parse_experience_levels(self):
        cases = [
            ("Fresher", "fresher"),
            ("0-2 yrs", "junior"),
            ("3-5 yrs", "mid"),
            ("5+ yrs", "senior"),
            ("Junior", "junior"),
            ("Intern", "intern"),
            ("unknown", "entry"),
        ]
        for text, expected in cases:
            assert self.scraper._parse_experience_level(text) == expected, text

    def test_parse_job_types(self):
        assert self.scraper._parse_job_type("Internship") == "internship"
        assert self.scraper._parse_job_type("Contract") == "contract"
        assert self.scraper._parse_job_type("Part Time") == "part_time"
        assert self.scraper._parse_job_type("Whatever") == "full_time"

    def test_city_detection(self):
        for city in ["Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai"]:
            job_data = {
                "title": "Analyst",
                "companyName": "Acme",
                "jobId": f"c-{city}",
                "placeholders": [{"type": "location", "label": f"{city}, India"}],
            }
            job = self.scraper._parse_job_data(job_data)
            assert job.city == city


class TestNaukriScrape:
    @pytest.mark.asyncio
    async def test_scrape_returns_jobs(self, monkeypatch):
        scraper = NaukriScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobData": [
                        {
                            "title": "SOC Analyst",
                            "companyName": "Acme",
                            "jobId": "100",
                            "jobUrl": "https://naukri.com/job/100",
                        }
                    ],
                    "totalCount": 100,
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "100"

    @pytest.mark.asyncio
    async def test_scrape_deduplicates_jobs(self, monkeypatch):
        scraper = NaukriScraper()

        class FakeResponse:
            def json(self):
                return {
                    "jobData": [{"title": "Same Job", "companyName": "Acme", "jobId": "42"}],
                    "totalCount": 100,
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["a", "b"], max_pages=1)
        assert len(jobs) == 1  # same job id deduplicated across keywords

    @pytest.mark.asyncio
    async def test_scrape_empty_results_breaks(self, monkeypatch):
        scraper = NaukriScraper()

        class FakeResponse:
            def json(self):
                return {"jobData": [], "totalCount": 0}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=3)
        assert jobs == []

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = NaukriScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert jobs == []

    @pytest.mark.asyncio
    async def test_scrape_respects_total_count(self, monkeypatch):
        scraper = NaukriScraper()
        calls: list[str] = []

        class FakeResponse:
            def json(self):
                return {
                    "jobData": [{"title": "Job", "companyName": "Acme", "jobId": f"{len(calls)}"}],
                    "totalCount": 100,
                }

        async def fake_fetch(url, **kwargs):
            calls.append(url)
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=5)
        # totalCount 100 with 100/page -> only page 1 fetched (100 >= 100)
        assert len(calls) == 1
        assert len(jobs) == 1
