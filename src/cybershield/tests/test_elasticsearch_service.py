"""
Unit Tests for Elasticsearch Service

Tests the Elasticsearch service covering:
- Availability detection
- Search query building (when ES unavailable, returns fallback)
- Index operations
- Graceful fallback behavior
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.services import elasticsearch_service as es


class TestElasticsearchServiceAvailability:
    """Test Elasticsearch availability detection and fallback."""

    def setup_method(self):
        """Reset ES state before each test."""
        es._es_client = None
        es._es_available = False

    def test_not_available_by_default(self):
        """Elasticsearch should not be available by default."""
        assert es.is_available() is False

    @pytest.mark.asyncio
    async def test_init_fails_without_package(self):
        """Should gracefully handle missing elasticsearch package."""
        with patch.dict("sys.modules", {"elasticsearch": None}):
            result = await es.init_elasticsearch("http://localhost:9200")
            assert result is False
            assert es.is_available() is False

    @pytest.mark.asyncio
    async def test_init_fails_connection_error(self):
        """Should gracefully handle connection errors."""
        # Create a mock module to simulate elasticsearch being installed
        mock_es_module = MagicMock()
        mock_client = AsyncMock()
        mock_client.ping.return_value = False
        mock_es_module.AsyncElasticsearch.return_value = mock_client

        import sys

        sys.modules["elasticsearch"] = mock_es_module
        try:
            result = await es.init_elasticsearch("http://localhost:9200")
            assert result is False
        finally:
            del sys.modules["elasticsearch"]

    @pytest.mark.asyncio
    async def test_index_job_returns_false_when_unavailable(self):
        """Should return False when ES is not available."""
        result = await es.index_job({"id": "123", "title": "Test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_index_jobs_returns_zero_when_unavailable(self):
        """Should return 0 when ES is not available."""
        result = await es.index_jobs([{"id": "123"}])
        assert result == 0

    @pytest.mark.asyncio
    async def test_search_returns_fallback_when_unavailable(self):
        """Should return fallback response when ES is not available."""
        result = await es.search_jobs(query="security engineer")
        assert result["source"] == "database"
        assert result["results"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_delete_job_returns_false_when_unavailable(self):
        """Should return False when ES is not available."""
        result = await es.delete_job("123")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_index_stats_returns_unavailable(self):
        """Should return unavailable status when ES is not connected."""
        stats = await es.get_index_stats()
        assert stats["available"] is False


class TestElasticsearchSearchQuery:
    """Test search query building with mocked ES client."""

    def setup_method(self):
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_search_with_query(self):
        """Should build correct multi_match query."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response

        es._es_client = mock_client
        es._es_available = True

        await es.search_jobs(query="security engineer")

        # Verify search was called
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args
        query = call_kwargs.kwargs.get("query") or call_kwargs[1].get("query")

        # Should have multi_match in must clause
        assert "bool" in query
        must = query["bool"]["must"]
        assert any("multi_match" in clause for clause in must)

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Should build correct filter clauses."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response

        es._es_client = mock_client
        es._es_available = True

        await es.search_jobs(
            company="CrowdStrike",
            country="USA",
            is_remote=True,
            min_salary=80000,
        )

        call_kwargs = mock_client.search.call_args
        query = call_kwargs.kwargs.get("query") or call_kwargs[1].get("query")
        filter_clauses = query["bool"]["filter"]

        # Should have 4 filter clauses
        assert len(filter_clauses) == 4

        # Check specific filters exist
        filter_str = str(filter_clauses)
        assert "CrowdStrike" in filter_str
        assert "USA" in filter_str

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_search_with_skills(self):
        """Should handle skills filter correctly."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response

        es._es_client = mock_client
        es._es_available = True

        await es.search_jobs(skills=["Python", "AWS"])

        call_kwargs = mock_client.search.call_args
        query = call_kwargs.kwargs.get("query") or call_kwargs[1].get("query")
        filter_clauses = query["bool"]["filter"]

        # Should have terms filter for skills
        skills_filter = [
            f for f in filter_clauses if "terms" in f and "required_skills" in f.get("terms", {})
        ]
        assert len(skills_filter) == 1
        assert skills_filter[0]["terms"]["required_skills"] == ["Python", "AWS"]

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_search_parses_aggregations(self):
        """Should parse aggregation buckets correctly."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {
                "by_company": {
                    "buckets": [
                        {"key": "CrowdStrike", "doc_count": 15},
                        {"key": "McAfee", "doc_count": 10},
                    ]
                },
                "salary_stats": {"value": {"min": 60000, "max": 150000}},
            },
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response

        es._es_client = mock_client
        es._es_available = True

        result = await es.search_jobs(query="security")

        assert "aggregations" in result
        assert "by_company" in result["aggregations"]
        assert len(result["aggregations"]["by_company"]) == 2
        assert result["aggregations"]["by_company"][0]["key"] == "CrowdStrike"
        assert result["aggregations"]["by_company"][0]["count"] == 15

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        """Should handle ES exceptions gracefully."""
        mock_client = AsyncMock()
        mock_client.search.side_effect = Exception("Connection lost")

        es._es_client = mock_client
        es._es_available = True

        result = await es.search_jobs(query="test")
        assert result["source"] == "error"
        assert result["results"] == []

        # Clean up
        es._es_client = None
        es._es_available = False


class TestElasticsearchIndexing:
    """Test indexing operations with mocked ES client."""

    def setup_method(self):
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_index_job_success(self):
        """Should index a job successfully."""
        mock_client = AsyncMock()
        mock_client.index.return_value = {"result": "created"}

        es._es_client = mock_client
        es._es_available = True

        result = await es.index_job({"id": "123", "title": "Security Engineer"})
        assert result is True
        mock_client.index.assert_called_once()

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_index_job_no_id_returns_false(self):
        """Should return False for jobs without ID."""
        es._es_client = AsyncMock()
        es._es_available = True

        result = await es.index_job({"title": "No ID Job"})
        assert result is False

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_close_elasticsearch(self):
        """Should close the ES client cleanly."""
        mock_client = AsyncMock()
        es._es_client = mock_client
        es._es_available = True

        await es.close_elasticsearch()
        assert es._es_client is None
        assert es._es_available is False
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_elasticsearch_handles_error(self):
        """Should not raise when closing a broken client."""
        mock_client = AsyncMock()
        mock_client.close.side_effect = RuntimeError("boom")
        es._es_client = mock_client
        es._es_available = True

        await es.close_elasticsearch()
        assert es._es_client is None
        assert es._es_available is False

    @pytest.mark.asyncio
    async def test_index_jobs_skips_missing_ids(self):
        """Bulk indexing should skip jobs without an ID and return 0."""
        mock_client = AsyncMock()
        es._es_client = mock_client
        es._es_available = True

        result = await es.index_jobs([{"title": "no id"}, {"title": "also no id"}])
        assert result == 0

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_index_jobs_handles_bulk_error(self):
        """Bulk indexing should fall back to 0 when async_bulk raises."""
        import sys
        import types

        mock_client = AsyncMock()
        es._es_client = mock_client
        es._es_available = True

        # Inject a fake elasticsearch module whose async_bulk raises
        fake_helpers = types.ModuleType("elasticsearch.helpers")
        fake_helpers.async_bulk = AsyncMock(side_effect=RuntimeError("es down"))  # type: ignore[attr-defined]
        fake_es = types.ModuleType("elasticsearch")
        fake_es.helpers = fake_helpers  # type: ignore[attr-defined]
        sys.modules["elasticsearch"] = fake_es
        sys.modules["elasticsearch.helpers"] = fake_helpers
        try:
            result = await es.index_jobs([{"id": "1", "title": "Test"}])
        finally:
            del sys.modules["elasticsearch"]
            del sys.modules["elasticsearch.helpers"]
        assert result == 0

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_search_without_query_uses_match_all(self):
        """A search without a text query uses match_all."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response

        es._es_client = mock_client
        es._es_available = True

        await es.search_jobs()

        call_kwargs = mock_client.search.call_args
        query = call_kwargs.kwargs.get("query") or call_kwargs[1].get("query")
        must = query["bool"]["must"]
        assert any("match_all" in clause for clause in must)

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_delete_job_success(self):
        """Should delete a job and return True."""
        mock_client = AsyncMock()
        mock_client.delete.return_value = {"result": "deleted"}
        es._es_client = mock_client
        es._es_available = True

        result = await es.delete_job("123")
        assert result is True
        mock_client.delete.assert_called_once()

        # Clean up
        es._es_client = None
        es._es_available = False

    @pytest.mark.asyncio
    async def test_get_index_stats_success(self):
        """Should return document count from stats API."""
        mock_client = AsyncMock()
        mock_client.indices.stats.return_value = {
            "indices": {"cybershield_jobs": {"total": {"docs": {"count": 42}}}}
        }
        es._es_client = mock_client
        es._es_available = True

        stats = await es.get_index_stats()
        assert stats["available"] is True
        assert stats["document_count"] == 42

        # Clean up
        es._es_client = None
        es._es_available = False
