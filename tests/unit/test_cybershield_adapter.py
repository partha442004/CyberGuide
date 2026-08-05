"""Tests for interntrack.scrapers.cybershield_adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from interntrack.scrapers.cybershield_adapter import CybershieldScraperAdapter


def _fake_scraped_job(**overrides):
    """Build a cybershield-style ScrapedJob stand-in with to_dict()."""
    base = {
        "title": "SOC Analyst Intern",
        "company_name": "SecureCorp",
        "location": "Bengaluru",
        "description": "Monitor SIEM and respond to incidents",
        "url": "https://securecorp.example/job/1",
        "apply_url": "https://securecorp.example/apply/1",
        "source": "internshala",
        "salary_min": 20000,
        "salary_max": 30000,
        "salary_currency": "INR",
        "is_remote": False,
        "job_type": "internship",
        "posting_date": None,
        "deadline": None,
        "required_skills": ["siem", "splunk"],
        "preferred_skills": [],
    }
    base.update(overrides)
    job = MagicMock()
    job.to_dict.return_value = base
    return job


class TestFetch:
    @pytest.mark.asyncio
    async def test_maps_scraped_job_to_raw_job(self):
        cyber = AsyncMock()
        cyber.scrape.return_value = [_fake_scraped_job()]
        adapter = CybershieldScraperAdapter("internshala", cyber)

        jobs = await adapter.fetch("cybersecurity")

        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "SOC Analyst Intern"
        assert job.company == "SecureCorp"
        assert job.url == "https://securecorp.example/apply/1"
        assert job.source == "internshala"
        assert job.salary_currency == "INR"
        assert job.tags == ["siem", "splunk"]

    @pytest.mark.asyncio
    async def test_filters_non_matching_jobs(self):
        cyber = AsyncMock()
        cyber.scrape.return_value = [
            _fake_scraped_job(title="Data Analyst"),
            _fake_scraped_job(title="SOC Analyst"),
        ]
        adapter = CybershieldScraperAdapter("naukri", cyber)

        jobs = await adapter.fetch("cybersecurity")

        assert len(jobs) == 1
        assert jobs[0].title == "SOC Analyst"

    @pytest.mark.asyncio
    async def test_skips_empty_titles(self):
        cyber = AsyncMock()
        cyber.scrape.return_value = [
            _fake_scraped_job(title=""),
            _fake_scraped_job(title="Penetration Tester"),
        ]
        adapter = CybershieldScraperAdapter("unstop", cyber)

        jobs = await adapter.fetch("cybersecurity")

        assert len(jobs) == 1
        assert jobs[0].title == "Penetration Tester"

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        cyber = AsyncMock()
        cyber.scrape.return_value = [
            _fake_scraped_job(title=f"Security Role {i}") for i in range(10)
        ]
        adapter = CybershieldScraperAdapter("freshersworld", cyber)

        jobs = await adapter.fetch("security", limit=3)

        assert len(jobs) == 3

    @pytest.mark.asyncio
    async def test_handles_scraper_that_rejects_max_pages(self):
        cyber = AsyncMock()

        async def scrape_without_max_pages(**kwargs):
            return [_fake_scraped_job()]

        cyber.scrape = scrape_without_max_pages

        adapter = CybershieldScraperAdapter("crowdstrike", cyber)
        jobs = await adapter.fetch("security")

        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_scraper_error_propagates_for_registry_handling(self):
        """Errors bubble up so the registry records the failed source."""
        cyber = AsyncMock()
        cyber.scrape.side_effect = RuntimeError("blocked")
        adapter = CybershieldScraperAdapter("internshala", cyber)

        with pytest.raises(RuntimeError):
            await adapter.fetch("cybersecurity")


class TestSourceName:
    def test_source_name_property(self):
        cyber = AsyncMock()
        adapter = CybershieldScraperAdapter("paloalto", cyber)
        assert adapter.source_name == "paloalto"
