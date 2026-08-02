"""
Unit tests for the Unstop scraper.

Covers search URL building, item parsing (hackathon/competition/job types,
remote detection, prize extraction), and the scrape loop against mocked
fetch responses.
"""

import pytest

from cybershield.scrapers.india.unstop import UnstopScraper


class TestUnstopScraper:
    def setup_method(self):
        self.scraper = UnstopScraper()

    def test_name_and_config(self):
        assert self.scraper.name == "unstop"
        assert self.scraper.config.rate_limit == 0.5
        assert self.scraper.config.max_retries == 3

    def test_build_search_url(self):
        url = self.scraper._build_search_url("CTF", page=2)
        assert "unstop.com/api/search" in url
        assert "query=CTF" in url
        assert "type=all" in url
        assert "page=2" in url

    def test_parse_hackathon(self):
        item = {
            "id": "h-1",
            "title": "Hack The Future CTF",
            "organization": {"name": "Cyber Society"},
            "slug": "hack-the-future",
            "location": "",
            "skills": ["CTF", "Python"],
            "start_date": "2024-06-01",
            "end_date": "2024-06-03",
            "description": "Capture the flag with Python and cryptography",
            "prize": "$10,000",
        }
        job = self.scraper._parse_job_data(item, "hackathon")
        assert job.title == "Hack The Future CTF"
        assert job.company_name == "Cyber Society"
        assert job.source == "unstop"
        assert job.source_id == "h-1"
        assert "hackathon" in (job.url or "")
        assert job.job_type == "hackathon"
        assert job.is_remote is True  # no location -> remote
        assert job.country == "India"
        assert "CTF" in job.required_skills
        assert "python" in [s.lower() for s in job.required_skills]
        assert job.raw_data["prize"] == "$10,000"
        assert job.posting_date is not None
        assert job.deadline is not None

    def test_parse_competition(self):
        item = {
            "id": "c-1",
            "title": "Cyber Quest",
            "organization": {"name": "Acme"},
            "slug": "cyber-quest",
            "location": "Online",
            "skills": [],
            "description": "Solve security challenges",
        }
        job = self.scraper._parse_job_data(item, "competition")
        assert job.job_type == "competition"
        assert "competitions" in (job.url or "")
        assert job.is_remote is True  # 'online' in location -> remote

    def test_parse_job_type(self):
        item = {
            "id": "j-1",
            "title": "Security Engineer",
            "organization": {"name": "Acme"},
            "slug": "security-engineer",
            "location": "Pune, India",
            "skills": ["SIEM"],
            "description": "",
        }
        job = self.scraper._parse_job_data(item, "jobs")
        assert job.job_type == "full_time"
        assert job.is_remote is False
        assert job.is_onsite is not None

    def test_parse_no_skills(self):
        item = {
            "id": "j-2",
            "title": "Analyst",
            "organization": {"name": "Acme"},
            "slug": "analyst",
            "location": "",
            "skills": [],
            "description": "",
        }
        job = self.scraper._parse_job_data(item, "jobs")
        assert job.required_skills == []
        assert job.posting_date is None

    @pytest.mark.asyncio
    async def test_scrape_collects_all_types(self, monkeypatch):
        scraper = UnstopScraper()

        class FakeResponse:
            def json(self):
                return {
                    "hackathons": [
                        {"id": "1", "title": "CTF", "organization": {"name": "A"}, "slug": "s1"}
                    ],
                    "competitions": [
                        {"id": "2", "title": "Quest", "organization": {"name": "A"}, "slug": "s2"}
                    ],
                    "jobs": [
                        {"id": "3", "title": "Job", "organization": {"name": "A"}, "slug": "s3"}
                    ],
                }

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 3
        types = {j.job_type for j in jobs}
        assert types == {"hackathon", "competition", "full_time"}

    @pytest.mark.asyncio
    async def test_scrape_deduplicates(self, monkeypatch):
        scraper = UnstopScraper()

        class FakeResponse:
            def json(self):
                return {"hackathons": [{"id": "42", "title": "Same", "slug": "same"}]}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["a", "b"], max_pages=1)
        assert len(jobs) == 1  # same id across keywords deduplicated

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = UnstopScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=1)
        assert jobs == []
