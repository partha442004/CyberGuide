"""
Unit tests for scraper base class and registry.
"""

from unittest.mock import MagicMock

from interntrack.scrapers.base import RawJob
from interntrack.scrapers.registry import ScraperRegistry, get_default_registry


class TestRawJob:
    """Tests for RawJob dataclass."""

    def test_raw_job_creation(self):
        """Test creating a RawJob."""
        job = RawJob(
            title="Python Developer",
            company="TechCorp",
            url="https://example.com/job/1",
        )

        assert job.title == "Python Developer"
        assert job.company == "TechCorp"
        assert job.url == "https://example.com/job/1"

    def test_raw_job_to_dict(self):
        """Test RawJob to_dict method."""
        job = RawJob(
            title="Test Job",
            company="Test Co",
            url="https://test.com",
        )

        result = job.to_dict()

        assert isinstance(result, dict)
        assert result["title"] == "Test Job"
        assert result["company"] == "Test Co"

    def test_raw_job_defaults(self):
        """Test RawJob default values."""
        job = RawJob(
            title="Job",
            company="Company",
            url="https://example.com",
        )

        assert job.description is None
        assert job.location is None
        assert job.salary_min is None
        assert job.salary_max is None
        assert job.tags == []
        assert job.source == "unknown"


class TestScraperRegistry:
    """Tests for ScraperRegistry."""

    def test_registry_creation(self):
        """Test creating a registry."""
        registry = ScraperRegistry()

        assert len(registry.list_sources()) == 0

    def test_register_scraper(self):
        """Test registering a scraper."""
        registry = ScraperRegistry()
        mock_scraper = MagicMock()
        mock_scraper.source_name = "test_source"

        registry.register(mock_scraper)

        assert "test_source" in registry.list_sources()

    def test_get_scraper(self):
        """Test getting a scraper by name."""
        registry = ScraperRegistry()
        mock_scraper = MagicMock()
        mock_scraper.source_name = "test_source"
        registry.register(mock_scraper)

        result = registry.get("test_source")

        assert result == mock_scraper

    def test_get_nonexistent_scraper(self):
        """Test getting a non-existent scraper."""
        registry = ScraperRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_unregister_scraper(self):
        """Test unregistering a scraper."""
        registry = ScraperRegistry()
        mock_scraper = MagicMock()
        mock_scraper.source_name = "test_source"
        registry.register(mock_scraper)

        registry.unregister("test_source")

        assert "test_source" not in registry.list_sources()

    def test_get_all_scrapers(self):
        """Test getting all scrapers."""
        registry = ScraperRegistry()
        mock1 = MagicMock()
        mock1.source_name = "source1"
        mock2 = MagicMock()
        mock2.source_name = "source2"
        registry.register(mock1)
        registry.register(mock2)

        scrapers = registry.get_all()

        assert len(scrapers) == 2

    def test_list_sources(self):
        """Test listing sources."""
        registry = ScraperRegistry()
        mock1 = MagicMock()
        mock1.source_name = "source1"
        mock2 = MagicMock()
        mock2.source_name = "source2"
        registry.register(mock1)
        registry.register(mock2)

        sources = registry.list_sources()

        assert "source1" in sources
        assert "source2" in sources


class TestGetDefaultRegistry:
    """Tests for get_default_registry function."""

    def test_default_registry_has_scrapers(self):
        """Test that default registry has all scrapers."""
        registry = get_default_registry()

        sources = registry.list_sources()

        assert "hackernews" in sources
        assert "remote_ok" in sources
        assert "rss_feed" in sources
