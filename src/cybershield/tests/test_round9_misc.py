"""
Round 9 unit tests covering the last small uncovered branches across several
cybershield / interntrack modules:

- ``scrapers/base.py`` (base_url property, cache-failure warning, ``_fetch``
  delegation, abstract ``scrape`` body)
- ``scrapers/companies/checkpoint.py`` (``_fetch_search_page``)
- ``scrapers/usa/indeed.py`` (parse-card exception, viewjob job-id regex)
- ``engines/classification.py`` (1-year experience -> entry; skill categories)
- ``notifications/orchestrator.py`` (send_to_all fallbacks)
- ``scrapers/india/naukri.py`` (salary parse exception, "0" experience)
- ``repositories/base.py`` (order_by path, list-filter count)
- ``interntrack/services/ai_service.py`` (Ollama error, learning-path fallback)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.engines.classification import ClassificationEngine
from cybershield.repositories.base import BaseRepository
from cybershield.scrapers.base import BaseScraper, ScraperConfig


class TestBaseScraperRound9:
    """base_url property, _fetch delegation, cache-failure and abstract body."""

    @pytest.fixture
    def scraper(self):
        config = ScraperConfig(
            name="test",
            base_url="https://test.example",
            rate_limit=0,
        )

        class _S(BaseScraper):
            async def scrape(self, **kwargs):  # pragma: no cover - overridden
                return await super().scrape(**kwargs)  # type: ignore[safe-super]

        return _S(config)

    def test_base_url_property(self, scraper):
        assert scraper.base_url == "https://test.example"

    @pytest.mark.asyncio
    async def test_fetch_delegates_to_do_fetch(self, scraper):
        response = MagicMock()
        scraper._do_fetch = AsyncMock(return_value=response)
        result = await scraper._fetch("https://test.example/jobs")
        assert result is response
        scraper._do_fetch.assert_awaited_once_with("https://test.example/jobs", None, None)

    @pytest.mark.asyncio
    async def test_fetch_with_cache_handles_cache_write_error(self, scraper):
        response = MagicMock()
        response.status_code = 200
        response.text = "<html>jobs</html>"
        response.headers = {"content-type": "text/html"}
        scraper._do_fetch = AsyncMock(return_value=response)

        with (
            patch(
                "cybershield.scrapers.base.cache_manager.get_json",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "cybershield.scrapers.base.cache_manager.set_json",
                new_callable=AsyncMock,
                side_effect=RuntimeError("redis down"),
            ),
            patch("cybershield.scrapers.base.logger") as mock_logger,
        ):
            result = await scraper._fetch_with_cache("https://test.example/jobs")

        assert result is response
        mock_logger.warning.assert_called_once()
        assert "Failed to cache response" in mock_logger.warning.call_args.args[0]

    @pytest.mark.asyncio
    async def test_abstract_scrape_body_returns_none(self):
        config = ScraperConfig(name="t", base_url="https://x.example", rate_limit=0)

        class _S(BaseScraper):
            async def scrape(self, **kwargs):
                return await super().scrape(**kwargs)  # type: ignore[safe-super]

        result = await _S(config).scrape()
        assert result is None


class TestCheckpointRound9:
    """_fetch_search_page builds the search URL and returns response text."""

    @pytest.mark.asyncio
    async def test_fetch_search_page_builds_url(self):
        from cybershield.scrapers.companies.checkpoint import CheckPointScraper

        scraper = CheckPointScraper()
        response = MagicMock()
        response.text = "<html>results</html>"
        scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]
        scraper._rate_limit_wait = AsyncMock()  # type: ignore[method-assign]

        html = await scraper._fetch_search_page("security", page=2)

        assert html == "<html>results</html>"
        url = scraper._fetch.await_args.args[0]  # type: ignore[union-attr]
        assert "q=security" in url
        assert "page=2" in url
        scraper._rate_limit_wait.assert_awaited_once()


class TestUsaIndeedRound9:
    """Parse-card exception path and /viewjob job-id extraction."""

    def test_extract_job_id_viewjob_regex(self):
        from cybershield.scrapers.usa.indeed import IndeedScraper

        scraper = IndeedScraper()
        assert scraper._extract_job_id("https://indeed.com/viewjob?jk=abc123def") == ("abc123def")

    @pytest.mark.asyncio
    async def test_parse_card_exception_returns_none(self):
        from cybershield.scrapers.usa.indeed import IndeedScraper

        scraper = IndeedScraper()
        broken_card = MagicMock()
        broken_card.find.side_effect = RuntimeError("boom")
        with patch("cybershield.scrapers.usa.indeed.logger"):
            result = scraper._parse_job_card(broken_card)
        assert result is None


class TestClassificationRound9:
    """1-year experience and remaining skill categories."""

    @pytest.fixture
    def engine(self):
        return ClassificationEngine()

    def test_one_year_experience_is_entry(self, engine):
        assert engine._classify_experience_level("1 year experience") == {
            "level": "entry",
            "confidence": 0.7,
        }

    def test_skill_category_concepts(self, engine):
        assert engine._get_skill_category("OWASP") == "concepts"
        assert engine._get_skill_category("MITRE ATT&CK") == "concepts"

    def test_skill_category_other(self, engine):
        assert engine._get_skill_category("MS-Excel") == "other"


class TestOrchestratorRound9:
    """send_to_all fallback branches in scam alert, digest and report."""

    @pytest.mark.asyncio
    async def test_send_scam_alert_falls_back_to_all(self):
        from cybershield.notifications.orchestrator import NotificationOrchestrator

        orchestrator = NotificationOrchestrator()
        orchestrator.get_enabled_channels = MagicMock(return_value=["telegram", "email"])  # type: ignore[method-assign]
        orchestrator.send_to_channels = AsyncMock(return_value={"email": True})  # type: ignore[method-assign]
        orchestrator._format_job_content = MagicMock(return_value="job")  # type: ignore[method-assign]

        job = {"title": "Scam", "url": "https://x.example/job"}
        result = await orchestrator.send_scam_alert(job, scam_score=85.0)

        assert result == {"email": True}
        orchestrator.send_to_channels.assert_awaited_once()
        (channels, _message) = orchestrator.send_to_channels.await_args.args  # type: ignore[union-attr]
        assert "telegram" not in channels

    @pytest.mark.asyncio
    async def test_send_daily_digest_falls_back_to_all(self):
        from cybershield.notifications.orchestrator import NotificationOrchestrator

        orchestrator = NotificationOrchestrator()
        orchestrator.get_enabled_channels = MagicMock(return_value=["telegram"])  # type: ignore[method-assign]
        orchestrator.send_to_channels = AsyncMock(return_value={"telegram": True})  # type: ignore[method-assign]
        orchestrator._format_daily_digest = MagicMock(return_value="digest")  # type: ignore[method-assign]

        result = await orchestrator.send_daily_digest({"new_jobs": 3})

        assert result == {"telegram": True}
        orchestrator.send_to_channels.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_report_falls_back_to_all(self):
        from cybershield.notifications.orchestrator import NotificationOrchestrator

        orchestrator = NotificationOrchestrator()
        orchestrator.get_enabled_channels = MagicMock(return_value=["telegram"])  # type: ignore[method-assign]
        orchestrator.send_to_channels = AsyncMock(return_value={"telegram": True})  # type: ignore[method-assign]
        orchestrator._format_report = MagicMock(return_value="report")  # type: ignore[method-assign]

        result = await orchestrator.send_report("weekly", {"new_jobs": 5})

        assert result == {"telegram": True}
        orchestrator.send_to_channels.assert_awaited_once()


class TestNaukriRound9:
    """Salary parse exception and '0'-based fresher experience."""

    def test_parse_bad_salary_ignored_value_error(self):
        from cybershield.scrapers.india.naukri import NaukriScraper

        scraper = NaukriScraper()
        # "₹abc - ₹def" survives currency/separator stripping, so float()
        # conversion raises ValueError and is swallowed by the except clause.
        job_data = {"salaryDetails": {"label": "₹abc - ₹def PA"}}
        with patch("cybershield.scrapers.india.naukri.logger"):
            job = scraper._parse_job_data(job_data)
        assert job.salary_min is None
        assert job.salary_max is None

    def test_parse_experience_level_zero_means_fresher(self):
        from cybershield.scrapers.india.naukri import NaukriScraper

        scraper = NaukriScraper()
        assert scraper._parse_experience_level("0 yrs") == "fresher"


class TestRepositoryBaseRound9:
    """order_by path and list-filter count."""

    @pytest.mark.asyncio
    async def test_get_all_with_order_by(self, db_session):
        from cybershield.domain.models import Job

        # Use the in-memory test DB session and a real declarative model so the
        # SELECT/ORDER BY statement compiles without SQLAlchemy coercion errors.
        repo = BaseRepository(Job, db_session)
        rows = await repo.get_all(order_by="id", order_desc=False)
        assert isinstance(rows, list)

    @pytest.mark.asyncio
    async def test_count_with_list_filter(self, db_session):
        from cybershield.domain.models import Job

        repo = BaseRepository(Job, db_session)
        count = await repo.count({"is_active": [True]})
        assert count == 0


class TestInterntrackAiRound9:
    """Ollama error path and learning-path AI-unavailable fallback."""

    @pytest.mark.asyncio
    async def test_ollama_classification_error_returns_error_dict(self, monkeypatch):
        import interntrack.services.ai_service as ai_module

        service = ai_module.AIService(session=MagicMock())
        fake_httpx = MagicMock()
        client_ctx = MagicMock()
        client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
        client_ctx.__aexit__ = AsyncMock(return_value=None)
        client_ctx.post = AsyncMock(side_effect=RuntimeError("ollama down"))
        fake_httpx.AsyncClient.return_value = client_ctx

        mock_settings = MagicMock()
        mock_settings.ollama_base_url = "http://localhost:11434"
        monkeypatch.setattr(ai_module, "settings", mock_settings)
        monkeypatch.setattr(ai_module, "logger", MagicMock())

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await service._classify_with_ollama("prompt")

        assert result == {"error": "Ollama classification failed"}

    @pytest.mark.asyncio
    async def test_generate_learning_path_unavailable(self, monkeypatch):
        import interntrack.services.ai_service as ai_module

        service = ai_module.AIService(session=MagicMock())
        service._classify_with_gemini = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("no key")
        )
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "key"
        mock_settings.ollama_base_url = None
        monkeypatch.setattr(ai_module, "settings", mock_settings)
        monkeypatch.setattr(ai_module, "logger", MagicMock())

        result = await service.generate_learning_path(["python"], "SOC Analyst")

        assert result == {"steps": [], "message": "AI service not configured"}
