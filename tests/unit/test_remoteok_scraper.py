"""Unit tests for scrapers/remoteok.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestRemoteOKScraper:
    """Tests for RemoteOKScraper class."""

    def test_source_name(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        assert scraper.source_name == "remote_ok"

    def test_rate_limit(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        assert scraper.rate_limit == 30

    def test_parse_salary_range(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        salary_min, salary_max = scraper._parse_salary("$80,000 - $120,000")
        assert salary_min == 80000
        assert salary_max == 120000

    def test_parse_salary_single_value(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        salary_min, salary_max = scraper._parse_salary("$80,000")
        assert salary_min == 80000
        assert salary_max == 80000

    def test_parse_salary_no_match(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        salary_min, salary_max = scraper._parse_salary("Competitive")
        assert salary_min is None
        assert salary_max is None

    def test_parse_date_valid(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        result = scraper._parse_date(1672531200)
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_date_none(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        result = scraper._parse_date(None)
        assert result is None

    def test_parse_job_returns_none_for_no_match(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        item = {
            "position": "Java Developer",
            "company": "TechCorp",
            "description": "Java experience required",
        }
        result = scraper._parse_job(item, "python")
        assert result is None

    def test_parse_job_returns_job_for_match(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        item = {
            "id": 123,
            "position": "Python Developer",
            "company": "TechCorp",
            "description": "Python and Django experience",
            "url": "https://remoteok.com/l/123",
            "location": "Remote",
            "salary": "$80,000 - $120,000",
            "epoch": 1672531200,
            "tags": ["python", "django"],
        }
        result = scraper._parse_job(item, "python")
        assert result is not None
        assert result.title == "Python Developer"
        assert result.company == "TechCorp"
        assert result.source == "remote_ok"
        assert result.is_remote is True
        assert result.salary_min == 80000
        assert result.salary_max == 120000

    def test_parse_job_generates_url(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        item = {
            "position": "Python Developer",
            "company": "TechCorp",
            "description": "Python experience",
        }
        result = scraper._parse_job(item, "python")
        assert result is not None
        assert "remoteok.com" in result.url

    def test_parse_job_no_salary(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        item = {
            "position": "Python Developer",
            "company": "TechCorp",
            "description": "Python experience",
        }
        result = scraper._parse_job(item, "python")
        assert result is not None
        assert result.salary_min is None
        assert result.salary_max is None

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        scraper._get = AsyncMock(side_effect=Exception("Network error"))

        result = await scraper.fetch("python")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_returns_jobs(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"api": "metadata"},
            {
                "position": "Python Developer",
                "company": "TechCorp",
                "description": "Python and Django",
                "tags": ["python"],
            },
            {
                "position": "React Developer",
                "company": "StartupInc",
                "description": "React experience",
                "tags": ["react"],
            },
        ]
        scraper._get = AsyncMock(return_value=mock_response)

        result = await scraper.fetch("python")
        assert len(result) == 1
        assert result[0].title == "Python Developer"
