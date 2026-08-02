"""
Extended tests for the ScraperRegistry.

Covers unregister, get_scraper instance caching, run_scraper,
run_region (concurrency + error isolation), run_all across regions,
and get_stats.
"""

from unittest.mock import MagicMock

import pytest

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig
from cybershield.scrapers.registry import ScraperRegistry


class _FakeScraper(BaseScraper):
    """Minimal concrete scraper stub for registry tests."""

    def __init__(self, config=None):
        super().__init__(config or ScraperConfig(name="fake", base_url="https://fake"))
        self.stats = {"name": "fake", "requests": 1, "errors": 0}

    async def scrape(self, **kwargs):
        return [ScrapedJob()]

    def get_stats(self):
        return self.stats


class TestRegistryLifecycle:
    def setup_method(self):
        # Save pristine state and clean up after each test.
        self._saved_scrapers = dict(ScraperRegistry._scrapers)
        self._saved_instances = dict(ScraperRegistry._instances)

    def teardown_method(self):
        ScraperRegistry._scrapers = dict(self._saved_scrapers)
        ScraperRegistry._instances = dict(self._saved_instances)

    def test_register_and_unregister(self):
        ScraperRegistry.register("fake_alpha", _FakeScraper)
        assert "fake_alpha" in ScraperRegistry.list_scrapers()

        ScraperRegistry.unregister("fake_alpha")
        assert "fake_alpha" not in ScraperRegistry.list_scrapers()

    def test_get_scraper_caches_instance(self):
        ScraperRegistry.register("fake_beta", _FakeScraper)
        first = ScraperRegistry.get_scraper("fake_beta")
        second = ScraperRegistry.get_scraper("fake_beta")
        assert first is second  # cached

    def test_get_scraper_new_instance_with_config(self):
        ScraperRegistry.register("fake_gamma", _FakeScraper)
        first = ScraperRegistry.get_scraper("fake_gamma")
        config = MagicMock()
        second = ScraperRegistry.get_scraper("fake_gamma", config=config)
        assert first is not second
        assert second.config is config

    def test_get_scraper_raises_for_unknown(self):
        with pytest.raises(ValueError):
            ScraperRegistry.get_scraper("does_not_exist")

    def test_get_stats_returns_instances(self):
        ScraperRegistry.register("fake_delta", _FakeScraper)
        ScraperRegistry.get_scraper("fake_delta")
        stats = ScraperRegistry.get_stats()
        assert "fake_delta" in stats
        assert stats["fake_delta"]["requests"] == 1

    def test_region_map(self):
        assert "naukri" in ScraperRegistry.get_scrapers_by_region("india")
        assert "indeed" in ScraperRegistry.get_scrapers_by_region("usa")
        assert "remoteok" in ScraperRegistry.get_scrapers_by_region("global")
        assert "company_microsoft" in ScraperRegistry.get_scrapers_by_region("companies")
        assert ScraperRegistry.get_scrapers_by_region("unknown") == []


class TestRegistryRun:
    def setup_method(self):
        self._saved_scrapers = dict(ScraperRegistry._scrapers)
        self._saved_instances = dict(ScraperRegistry._instances)

    def teardown_method(self):
        ScraperRegistry._scrapers = dict(self._saved_scrapers)
        ScraperRegistry._instances = dict(self._saved_instances)

    @pytest.mark.asyncio
    async def test_run_scraper_delegates(self):
        ScraperRegistry.register("fake_run", _FakeScraper)
        results = await ScraperRegistry.run_scraper("fake_run", max_pages=2)
        assert len(results) == 1
        assert isinstance(results[0], ScrapedJob)

    @pytest.mark.asyncio
    async def test_run_region_parallel(self):
        ScraperRegistry.register("fake_p1", _FakeScraper)
        ScraperRegistry.register("fake_p2", _FakeScraper)

        # Patch the region map so run_region picks up our fakes.
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                ScraperRegistry,
                "get_scrapers_by_region",
                classmethod(lambda cls, region: ["fake_p1", "fake_p2"]),
            )
            jobs = await ScraperRegistry.run_region("india")
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_run_region_unknown_returns_empty(self):
        jobs = await ScraperRegistry.run_region("nope")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_run_region_isolates_errors(self):
        class Boom(_FakeScraper):
            async def scrape(self, **kwargs):
                raise RuntimeError("boom")

        ScraperRegistry.register("fake_boom", Boom)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                ScraperRegistry,
                "get_scrapers_by_region",
                classmethod(lambda cls, region: ["fake_boom"]),
            )
            # Error inside one scraper must not propagate.
            jobs = await ScraperRegistry.run_region("india")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_run_all_iterates_regions(self):
        calls = []

        async def fake_run_region(cls, region, **kwargs):
            calls.append(region)
            return [{"source_id": f"{region}-1"}]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(ScraperRegistry, "run_region", classmethod(fake_run_region))
            jobs = await ScraperRegistry.run_all(regions=["india", "usa"])
        assert calls == ["india", "usa"]
        assert len(jobs) == 2
