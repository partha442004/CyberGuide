"""Tests targeting low-coverage areas to push toward 90%+."""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ─── Scraper Registry ───────────────────────────────────────────────────────


class TestScraperRegistryExtended:
    """Extended tests for scrapers/registry.py to boost coverage."""

    def test_get_all_scrapers(self):
        from interntrack.scrapers.registry import ScraperRegistry

        registry = ScraperRegistry()
        mock1 = MagicMock()
        mock1.source_name = "s1"
        mock2 = MagicMock()
        mock2.source_name = "s2"
        registry.register(mock1)
        registry.register(mock2)

        assert len(registry.get_all()) == 2

    def test_unregister_nonexistent(self):
        from interntrack.scrapers.registry import ScraperRegistry

        registry = ScraperRegistry()
        # Should not raise
        registry.unregister("nonexistent")

    def test_get_default_registry(self):
        from interntrack.scrapers.registry import get_default_registry

        registry = get_default_registry()

        sources = registry.list_sources()
        assert "hackernews" in sources
        assert "rss_feed" in sources
        assert "linkedin" in sources
        assert "indeed" in sources
        assert "glassdoor" in sources
        assert "remote_ok" not in sources  # RemoteOK API returns junk now
        assert len(sources) == 5

    @pytest.mark.asyncio
    async def test_fetch_all_no_sources(self):
        from interntrack.scrapers.registry import ScraperRegistry

        registry = ScraperRegistry()
        mock_scraper = MagicMock()
        mock_scraper.source_name = "test"
        mock_scraper.fetch = AsyncMock(return_value=[])
        registry.register(mock_scraper)

        result = await registry.fetch_all(query="python")

        assert result == []
        mock_scraper.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_all_with_source_filter(self):
        from interntrack.scrapers.registry import ScraperRegistry

        registry = ScraperRegistry()
        mock1 = MagicMock()
        mock1.source_name = "s1"
        mock1.fetch = AsyncMock(return_value=[])
        mock2 = MagicMock()
        mock2.source_name = "s2"
        mock2.fetch = AsyncMock(return_value=[])
        registry.register(mock1)
        registry.register(mock2)

        await registry.fetch_all(query="python", sources=["s1"])

        mock1.fetch.assert_called_once()
        mock2.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_all_scraper_error(self):
        from interntrack.scrapers.registry import ScraperRegistry

        registry = ScraperRegistry()
        mock_scraper = MagicMock()
        mock_scraper.source_name = "failing"
        mock_scraper.fetch = AsyncMock(side_effect=Exception("Network error"))
        registry.register(mock_scraper)

        # Should not raise, just continue
        result = await registry.fetch_all(query="python")

        assert result == []

    @pytest.mark.asyncio
    async def test_close_all(self):
        from interntrack.scrapers.registry import ScraperRegistry

        registry = ScraperRegistry()
        mock1 = MagicMock()
        mock1.source_name = "s1"
        mock1.close = AsyncMock()
        mock2 = MagicMock()
        mock2.source_name = "s2"
        mock2.close = AsyncMock()
        registry.register(mock1)
        registry.register(mock2)

        await registry.close_all()

        mock1.close.assert_called_once()
        mock2.close.assert_called_once()


# ─── Report Service ─────────────────────────────────────────────────────────


class TestReportServiceExtended:
    """Extended tests for services/report_service.py."""

    @pytest.mark.asyncio
    async def test_generate_daily_report(self):
        from unittest.mock import MagicMock as Mock

        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        # Mock job count
        mock_result = Mock()
        mock_result.scalar.return_value = 10
        session.execute.return_value = mock_result

        result = await service.generate_daily_report()

        assert result["report_type"] == "daily"
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_generate_weekly_report(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        session.execute.return_value = mock_result

        result = await service.generate_weekly_report()

        assert result["report_type"] == "weekly"
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_generate_monthly_report(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        mock_result = MagicMock()
        mock_result.scalar.return_value = 20
        session.execute.return_value = mock_result

        result = await service.generate_monthly_report()

        assert result["report_type"] == "monthly"
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_render_report(self):
        from interntrack.services.report_service import ReportService

        session = AsyncMock()
        service = ReportService(session)

        data = {
            "report_type": "daily",
            "generated_at": "2026-01-01",
            "summary": {"new_jobs": 5, "new_applications": 3, "total_applications": 10},
            "new_jobs": [],
            "closing_soon": [],
            "application_status": {},
        }

        html = await service.render_report(data)

        assert isinstance(html, str)
        assert len(html) > 0


# ─── Classification Engine — classify_job main path ─────────────────────────


class TestClassificationEngineMainPath:
    """Tests for the classify_job main path in classification.py."""

    @pytest.mark.asyncio
    async def test_classify_job_ai_success_with_skills(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        engine.ai_service.classify_job = AsyncMock(
            return_value={
                "job_type": "full_time",
                "experience_level": "mid",
                "skills": ["python", "django", "docker"],
                "is_remote": False,
                "confidence": 0.9,
            },
        )

        mock_skill = MagicMock()
        mock_skill.id = "s1"
        mock_skill.name = "python"
        mock_skill.category.value = "programming"

        engine.skill_repo.create_or_get = AsyncMock(return_value=mock_skill)

        result = await engine.classify_job(
            {
                "title": "Python Developer",
                "description": "Build APIs with Python and Django.",
            },
        )

        assert result["job_type"] == "full_time"
        assert result["confidence"] == 0.9
        assert "matched_skills" in result
        assert len(result["matched_skills"]) >= 1

    @pytest.mark.asyncio
    async def test_classify_job_ai_failure_fallback(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        engine.ai_service.classify_job = AsyncMock(
            return_value={"error": "AI unavailable"},
        )

        result = await engine.classify_job(
            {
                "title": "Senior Python Developer",
                "description": "Remote work available.",
            },
        )

        assert result["job_type"] == "remote"
        assert result["experience_level"] == "senior"
        assert result["is_remote"] is True

    @pytest.mark.asyncio
    async def test_classify_job_with_description_skills(self):
        from interntrack.engines.classification import ClassificationEngine

        session = AsyncMock()
        engine = ClassificationEngine(session)

        engine.ai_service.classify_job = AsyncMock(
            return_value={
                "job_type": "full_time",
                "experience_level": "junior",
                "skills": [],
                "is_remote": False,
                "confidence": 0.6,
            },
        )

        mock_skill = MagicMock()
        mock_skill.id = "s1"
        mock_skill.name = "react"
        mock_skill.category.value = "framework"

        engine.skill_repo.create_or_get = AsyncMock(return_value=mock_skill)

        result = await engine.classify_job(
            {
                "title": "Junior Frontend Developer",
                "description": "React and TypeScript experience required.",
            },
        )

        assert "matched_skills" in result
        assert len(result["matched_skills"]) >= 1
