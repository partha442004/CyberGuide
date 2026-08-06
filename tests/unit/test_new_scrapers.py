"""
Tests for new scrapers: Hired, AngelList, Indeed API, LinkedIn Jobs API.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.scrapers.angellist import AngelListScraper
from interntrack.scrapers.hired import HiredScraper
from interntrack.scrapers.indeed_api import IndeedAPIScraper
from interntrack.scrapers.linkedin_jobs_api import LinkedInJobsAPIScraper


class TestHiredScraper:
    """Tests for Hired scraper."""

    def test_source_name(self):
        scraper = HiredScraper()
        assert scraper.source_name == "hired"

    def test_rate_limit(self):
        scraper = HiredScraper()
        assert scraper.rate_limit == 20

    @pytest.mark.asyncio
    async def test_fetch_returns_jobs(self):
        scraper = HiredScraper()

        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <div class="job-card">
                <h2 class="job-title">Security Engineer</h2>
                <span class="company-name">Google</span>
                <a class="job-link" href="/jobs/123">Apply</a>
                <span class="location">Bangalore, India</span>
                <span class="salary">$100k - $150k</span>
            </div>
        </html>
        """

        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_response)):
            jobs = await scraper.fetch("security", limit=5)
            assert len(jobs) > 0
            assert jobs[0].source == "hired"
            assert jobs[0].company == "Google"

    @pytest.mark.asyncio
    async def test_fetch_handles_errors(self):
        scraper = HiredScraper()

        with patch.object(
            scraper, "_get", new=AsyncMock(side_effect=Exception("Network error"))
        ):
            jobs = await scraper.fetch("security", limit=5)
            assert jobs == []

    def test_parse_salary(self):
        scraper = HiredScraper()
        assert scraper._parse_salary("$100k - $150k") == (100000, 150000)
        assert scraper._parse_salary("$80k") == (80000, 80000)
        assert scraper._parse_salary("Not specified") == (None, None)


class TestAngelListScraper:
    """Tests for AngelList scraper."""

    def test_source_name(self):
        scraper = AngelListScraper()
        assert scraper.source_name == "angellist"

    def test_rate_limit(self):
        scraper = AngelListScraper()
        assert scraper.rate_limit == 15

    @pytest.mark.asyncio
    async def test_fetch_returns_jobs(self):
        scraper = AngelListScraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <div class="job-listing">
                <h2 class="job-title">Security Analyst</h2>
                <span class="company-name">StartupXYZ</span>
                <a class="job-link" href="/jobs/456">Apply</a>
                <span class="location">Remote</span>
                <span class="salary">$120k - $180k</span>
            </div>
        </html>
        """

        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_response)):
            jobs = await scraper.fetch("security analyst", limit=5)
            assert len(jobs) > 0
            assert jobs[0].source == "angellist"

    @pytest.mark.asyncio
    async def test_fetch_handles_errors(self):
        scraper = AngelListScraper()

        with patch.object(
            scraper, "_get", new=AsyncMock(side_effect=Exception("Error"))
        ):
            jobs = await scraper.fetch("security", limit=5)
            assert jobs == []


class TestIndeedAPIScraper:
    """Tests for Indeed API scraper."""

    def test_source_name(self):
        scraper = IndeedAPIScraper()
        assert scraper.source_name == "indeed_api"

    def test_rate_limit(self):
        scraper = IndeedAPIScraper()
        assert scraper.rate_limit == 15

    @pytest.mark.asyncio
    async def test_fetch_returns_jobs(self):
        scraper = IndeedAPIScraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <div class="job_seen_beacon">
                <h2 class="jobTitle"><a>Security Engineer</a></h2>
                <span class="companyName">Amazon</span>
                <div class="companyLocation">Bangalore, India</div>
                <span class="salaryText">₹15,00,000 - ₹25,00,000</span>
            </div>
        </html>
        """

        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_response)):
            jobs = await scraper.fetch("security engineer", limit=5)
            assert len(jobs) > 0
            assert jobs[0].source == "indeed_api"
            assert jobs[0].company == "Amazon"

    @pytest.mark.asyncio
    async def test_fetch_handles_errors(self):
        scraper = IndeedAPIScraper()

        with patch.object(
            scraper, "_get", new=AsyncMock(side_effect=Exception("Error"))
        ):
            jobs = await scraper.fetch("security", limit=5)
            assert jobs == []

    def test_parse_salary(self):
        scraper = IndeedAPIScraper()
        assert scraper._parse_salary("₹15,00,000 - ₹25,00,000") == (1500000, 2500000)


class TestLinkedInJobsAPIScraper:
    """Tests for LinkedIn Jobs API scraper."""

    def test_source_name(self):
        scraper = LinkedInJobsAPIScraper()
        assert scraper.source_name == "linkedin_jobs_api"

    def test_rate_limit(self):
        scraper = LinkedInJobsAPIScraper()
        assert scraper.rate_limit == 10

    @pytest.mark.asyncio
    async def test_fetch_returns_jobs(self):
        scraper = LinkedInJobsAPIScraper()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <li>
                <h3 class="base-search-card__title">Cyber Security Analyst</h3>
                <h4 class="base-search-card__subtitle">Microsoft</h4>
                <a class="hidden-nested-link" href="/jobs/view/789">Apply</a>
                <span class="job-search-card__location">Hyderabad, India</span>
            </li>
        </html>
        """

        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_response)):
            jobs = await scraper.fetch("cyber security", limit=5)
            assert len(jobs) > 0
            assert jobs[0].source == "linkedin_jobs_api"
            assert jobs[0].company == "Microsoft"

    @pytest.mark.asyncio
    async def test_fetch_handles_auth_wall(self):
        scraper = LinkedInJobsAPIScraper()

        mock_response = MagicMock()
        mock_response.status_code = 999
        mock_response.text = "authwall challenge"

        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_response)):
            jobs = await scraper.fetch("security", limit=5)
            assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_handles_errors(self):
        scraper = LinkedInJobsAPIScraper()

        with patch.object(
            scraper, "_get", new=AsyncMock(side_effect=Exception("Error"))
        ):
            jobs = await scraper.fetch("security", limit=5)
            assert jobs == []
