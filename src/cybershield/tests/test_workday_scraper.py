"""
Unit tests for the BaseWorkdayScraper.

Uses a concrete subclass (CrowdStrike-style) to exercise the Workday
search payload, job parsing (externalPath, locations, job types),
country detection for every branch, the Workday API fetch, and the
scrape loop against mocked HTTP responses.
"""

from unittest.mock import AsyncMock, patch

import pytest

from cybershield.scrapers.base import ScrapedJob
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper


class _FakeWorkdayScraper(BaseWorkdayScraper):
    CAREER_URL = "https://crowdstrike.wd5.myworkdayjobs.com/Careers"
    API_URL = "https://crowdstrike.wd5.myworkdayjobs.com/wday/cxs/crowdstrike/Careers/jobs"
    COMPANY_SLUG = "Careers"
    DEFAULT_KEYWORDS = ["security engineer"]

    def __init__(self, config=None):
        super().__init__(
            company_name="CrowdStrike",
            career_url=self.CAREER_URL,
            config=config,
        )


class TestWorkdayPayload:
    def setup_method(self):
        self.scraper = _FakeWorkdayScraper()

    def test_build_search_payload(self):
        payload = self.scraper._build_search_payload("security", page=2, limit=20)
        assert payload["searchText"] == "security"
        assert payload["limit"] == 20
        assert payload["offset"] == 40
        assert payload["appliedFacets"] == {}


class TestWorkdayParseJob:
    def setup_method(self):
        self.scraper = _FakeWorkdayScraper()

    def test_parse_job_with_external_path(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Security Engineer",
                "externalPath": "/wday/cxs/crowdstrike/Careers/job/1234",
                "locationsText": "Redmond, WA, United States",
                "timeType": "Full Time",
                "postedOn": "2024-03-01",
                "jobDescription": "Cloud security with Python",
            }
        )
        assert job.title == "Security Engineer"
        assert job.company_name == "CrowdStrike"
        assert job.source_id == "1234"
        assert "crowdstrike" in (job.url or "")
        assert "United States" in (job.url or "") or "1234" in (job.url or "")
        assert job.country == "USA"
        assert job.job_type == "full_time"
        assert job.experience_level == "mid"
        assert job.posting_date is not None

    def test_parse_job_part_time(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Analyst",
                "externalPath": "/job/999",
                "locationsText": "London, UK",
                "timeType": "Part Time",
            }
        )
        assert job.job_type == "part_time"
        assert job.country == "UK"

    def test_parse_job_no_external_path(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Analyst",
                "postedOn": "2024-01-15",
                "locationsText": "Berlin, Germany",
            }
        )
        assert job.source_id == "2024-01-15"
        assert job.url == self.scraper.career_url
        assert job.country == "Germany"

    def test_parse_job_no_location(self):
        job = self.scraper._parse_job_data({"title": "Analyst", "externalPath": "/job/1"})
        assert job.country == "Remote"
        assert job.location is None

    def test_parse_job_skills_from_description(self):
        job = self.scraper._parse_job_data(
            {
                "title": "Cloud Security",
                "externalPath": "/job/2",
                "locationsText": "Remote",
                "jobDescription": "Need AWS and Python expertise",
            }
        )
        names = [s.lower() for s in job.required_skills]
        assert "aws" in names
        assert "python" in names


class TestWorkdayCountryDetection:
    def setup_method(self):
        self.scraper = _FakeWorkdayScraper()

    def _country_for(self, text: str) -> str:
        job = ScrapedJob()
        self.scraper._detect_country(job, text)
        return job.country or ""

    def test_all_country_branches(self):
        assert self._country_for("Mountain View, CA, USA") == "USA"
        assert self._country_for("United States") == "USA"
        assert self._country_for("New York (US)") == "USA"
        assert self._country_for("Bangalore, India") == "India"
        assert self._country_for("Hyderabad, India") == "India"
        assert self._country_for("Remote") == "Remote"
        assert self._country_for("London, UK") == "UK"
        assert self._country_for("Berlin, Germany") == "Germany"
        assert self._country_for("Tel Aviv, Israel") == "Israel"
        assert self._country_for("Singapore") == "Singapore"
        assert self._country_for("Sydney, Australia") == "Australia"
        assert self._country_for("Toronto, Canada") == "Canada"
        assert self._country_for("Dubai") == "Global"

    def test_remote_sets_flag(self):
        job = ScrapedJob()
        self.scraper._detect_country(job, "Work From Home - Remote")
        assert job.is_remote is True
        assert job.country == "Remote"


class TestWorkdayFetch:
    @pytest.mark.asyncio
    async def test_fetch_workday_posts_and_parses(self):
        scraper = _FakeWorkdayScraper()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "jobPostings": [
                        {"title": "Security", "externalPath": "/job/1"},
                        "not-a-dict",
                        {"title": "Analyst", "externalPath": "/job/2"},
                    ]
                }

        mock_client = AsyncMock()
        mock_client.post.return_value = FakeResponse()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "cybershield.scrapers.companies.base_workday.httpx.AsyncClient",
            return_value=mock_client,
        ):
            postings = await scraper._fetch_workday("security", page=0, limit=20)

        assert len(postings) == 2  # non-dict entries filtered out
        mock_client.post.assert_awaited_once()
        call_kwargs = mock_client.post.await_args.kwargs
        assert call_kwargs["json"]["searchText"] == "security"
        assert call_kwargs["json"]["offset"] == 0

    @pytest.mark.asyncio
    async def test_fetch_workday_propagates_http_error(self):
        scraper = _FakeWorkdayScraper()

        class FakeResponse:
            def raise_for_status(self):
                raise RuntimeError("HTTP 500")

        mock_client = AsyncMock()
        mock_client.post.return_value = FakeResponse()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch(
            "cybershield.scrapers.companies.base_workday.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(RuntimeError):
                await scraper._fetch_workday("security")


class TestWorkdayScrape:
    @pytest.mark.asyncio
    async def test_scrape_collects_security_jobs(self, monkeypatch):
        scraper = _FakeWorkdayScraper()

        async def fake_fetch(keyword, page=0, limit=20):
            if page == 0:
                return [
                    {"title": "Security Engineer", "externalPath": "/job/1"},
                    {"title": "Marketing", "externalPath": "/job/2"},
                ]
            return []

        monkeypatch.setattr(scraper, "_fetch_workday", fake_fetch)
        jobs = await scraper.scrape(keywords=["security"], max_pages=2)
        assert len(jobs) == 1
        assert jobs[0].source_id == "1"

    @pytest.mark.asyncio
    async def test_scrape_handles_errors(self, monkeypatch):
        scraper = _FakeWorkdayScraper()

        async def fake_fetch(keyword, page=0, limit=20):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch_workday", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=1) == []
