"""
Round 9 test batch covering the last remaining scraper / API / engine
branches:

- company scrapers (cisco, microsoft, google, amazon): India/remote location
  detection, empty-result page breaks, and fetch-error breaks
- ``scrapers/india/freshersworld.py`` (bad salary ignored)
- ``interntrack/api/v1/jobs.py`` (invalid job-type, create-job 500)
- ``interntrack/config.py`` (``is_ai_configured`` property)
- ``notifications/orchestrator.py`` (send_scam_alert with channels)
- ``interntrack/engines/deduplication.py`` (seen-pair skip)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCompanyScraperBranches:
    """Location branches and scrape-loop breaks for the company scrapers."""

    @pytest.mark.asyncio
    async def test_cisco_parse_india_location(self):
        from cybershield.scrapers.companies.cisco import CiscoScraper

        job = CiscoScraper()._parse_job_data(
            {"title": "Analyst", "jobId": "c-1", "locations": ["Bengaluru, India"]}
        )
        assert job.country == "India"

    @pytest.mark.asyncio
    async def test_cisco_scrape_breaks_on_empty_page(self, monkeypatch):
        from cybershield.scrapers.companies.cisco import CiscoScraper

        scraper = CiscoScraper()

        class FakeResponse:
            def json(self):
                return {"jobRequisitions": {"requisitionList": []}}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=3) == []

    @pytest.mark.asyncio
    async def test_cisco_scrape_breaks_on_fetch_error(self, monkeypatch):
        from cybershield.scrapers.companies.cisco import CiscoScraper

        scraper = CiscoScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        with patch("cybershield.scrapers.companies.cisco.logger"):
            assert await scraper.scrape(keywords=["security"], max_pages=3) == []

    def test_microsoft_parse_india_and_remote(self):
        from cybershield.scrapers.companies.microsoft import MicrosoftScraper

        scraper = MicrosoftScraper()
        job_india = scraper._parse_job_data(
            {"title": "Analyst", "jobId": "m-1", "locations": ["Hyderabad, India"]}
        )
        assert job_india.country == "India"

        job_remote = scraper._parse_job_data(
            {"title": "Analyst", "jobId": "m-2", "locations": ["Remote"]}
        )
        assert job_remote.is_remote is True
        assert job_remote.country == "Remote"

    @pytest.mark.asyncio
    async def test_microsoft_scrape_breaks_on_empty_page(self, monkeypatch):
        from cybershield.scrapers.companies.microsoft import MicrosoftScraper

        scraper = MicrosoftScraper()

        class FakeResponse:
            def json(self):
                return {"operationResult": {"result": {"jobs": []}}}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=2) == []

    def test_google_parse_remote(self):
        from cybershield.scrapers.companies.google import GoogleScraper

        job = GoogleScraper()._parse_job_data(
            {"title": "Analyst", "id": "g-1", "locations": ["Remote"]}
        )
        assert job.is_remote is True
        assert job.country == "Remote"

    @pytest.mark.asyncio
    async def test_google_scrape_breaks_on_empty_page(self, monkeypatch):
        from cybershield.scrapers.companies.google import GoogleScraper

        scraper = GoogleScraper()

        class FakeResponse:
            def json(self):
                return {"jobs": []}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=2) == []

    @pytest.mark.asyncio
    async def test_google_scrape_breaks_on_fetch_error(self, monkeypatch):
        from cybershield.scrapers.companies.google import GoogleScraper

        scraper = GoogleScraper()

        async def fake_fetch(url, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        with patch("cybershield.scrapers.companies.google.logger"):
            assert await scraper.scrape(keywords=["security"], max_pages=2) == []

    @pytest.mark.asyncio
    async def test_amazon_scrape_breaks_on_empty_page(self, monkeypatch):
        from cybershield.scrapers.companies.amazon import AmazonScraper

        scraper = AmazonScraper()

        class FakeResponse:
            def json(self):
                return {"jobs": []}

        async def fake_fetch(url, **kwargs):
            return FakeResponse()

        monkeypatch.setattr(scraper, "_fetch", fake_fetch)
        assert await scraper.scrape(keywords=["security"], max_pages=2) == []


class TestFreshersworldRound9:
    """Bad salary strings are silently ignored."""

    def test_bad_salary_ignored(self):
        from cybershield.scrapers.india.freshersworld import FreshersworldScraper

        scraper = FreshersworldScraper()
        # "abc" survives symbol/separator stripping, so float() raises
        # ValueError and is swallowed by the except clause.
        job_data = {"salary": "₹abc LPA"}
        with patch("cybershield.scrapers.india.freshersworld.logger"):
            job = scraper._parse_job_data(job_data)
        assert job.salary_min is None
        assert job.salary_max is None


class TestInterntrackJobsApiRound9:
    """Invalid job type is ignored; create-job wraps errors as 500."""

    @pytest.mark.asyncio
    async def test_list_jobs_ignores_invalid_job_type(self):
        # Call the router function directly with a mocked service; the invalid
        # job_type is normalized to None inside the handler.
        from interntrack.api.v1.jobs import list_jobs

        service = MagicMock()
        service.get_jobs = AsyncMock(return_value=[])
        service.job_repo.count = AsyncMock(return_value=0)

        from interntrack.api.v1 import jobs as jobs_module

        with patch.object(jobs_module, "JobService", return_value=service):
            response = await list_jobs(
                job_type="not-a-real-type",
                skip=0,
                limit=20,
                is_remote=None,
                company=None,
                db=MagicMock(),
            )
        assert response.total == 0

    @pytest.mark.asyncio
    async def test_create_job_wraps_unknown_error_as_500(self):
        from fastapi import HTTPException
        from interntrack.api.v1.jobs import create_job

        service = MagicMock()
        service.create_job = AsyncMock(side_effect=RuntimeError("db down"))

        from interntrack.api.v1 import jobs as jobs_module

        job_data = MagicMock()
        job_data.model_dump.return_value = {"title": "T"}

        with patch.object(jobs_module, "JobService", return_value=service):
            with pytest.raises(HTTPException) as exc_info:
                await create_job(job_data, db=MagicMock())
        assert exc_info.value.status_code == 500


class TestInterntrackConfigRound9:
    """is_ai_configured reflects gemini/ollama configuration."""

    def test_is_ai_configured(self, monkeypatch):
        from interntrack.config import Settings

        settings = Settings(gemini_api_key="key")
        assert settings.is_ai_configured is True

        settings2 = Settings(gemini_api_key=None, ollama_base_url="")
        assert settings2.is_ai_configured is False


class TestOrchestratorChannelsRound9:
    """send_scam_alert with explicit channels uses send_to_channels."""

    @pytest.mark.asyncio
    async def test_send_scam_alert_with_channels(self):
        from cybershield.notifications.orchestrator import NotificationOrchestrator

        orchestrator = NotificationOrchestrator()
        orchestrator.send_to_channels = AsyncMock(  # type: ignore[method-assign]
            return_value={"email": True}
        )
        orchestrator._format_job_content = MagicMock(  # type: ignore[method-assign]
            return_value="job"
        )

        job = {"title": "Scam", "url": "https://x.example/job"}
        result = await orchestrator.send_scam_alert(job, scam_score=90.0, channels=["email"])

        assert result == {"email": True}
        orchestrator.send_to_channels.assert_awaited_once()


class TestInterntrackDedupSeenPairs:
    """find_duplicates_in_database skips already-seen duplicate pairs."""

    @pytest.mark.asyncio
    async def test_seen_pair_is_skipped(self):
        from interntrack.engines.deduplication import DeduplicationEngine

        session = MagicMock()
        result = MagicMock()
        job_a = MagicMock()
        job_a.id = "a"
        job_b = MagicMock()
        job_b.id = "b"
        job_c = MagicMock()
        job_c.id = "c"
        result.scalars.return_value.all.return_value = [job_a, job_b, job_c]
        session.execute = AsyncMock(return_value=result)

        engine = DeduplicationEngine(session)
        # All pairs are similar -> (a,b), (a,c), (b,c) reported.
        engine.calculate_similarity = MagicMock(  # type: ignore[method-assign]
            return_value=0.99
        )

        dupes = await engine.find_duplicates_in_database(threshold=0.9)

        assert len(dupes) == 3
        assert engine.calculate_similarity.call_count == 3
