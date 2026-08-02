"""
Unit Tests for Elasticsearch Service (extended)

Covers the remaining branches of ``cybershield/services/elasticsearch_service.py``:
- init_elasticsearch success path (ping OK + index creation)
- init exception path
- index_job / index_jobs error and success paths
- search with location / job_type / experience_level / max_salary filters
- delete_job and get_index_stats error paths
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from cybershield.services import elasticsearch_service as es


class TestInitElasticsearchSuccess:
    """Tests for the successful Elasticsearch initialization path."""

    @pytest.mark.asyncio
    async def test_init_creates_index_when_missing(self):
        """Should create the index and mark available when ping succeeds."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = False
        mock_client.indices.create = AsyncMock()

        mock_module = MagicMock()
        mock_module.AsyncElasticsearch.return_value = mock_client

        sys.modules["elasticsearch"] = mock_module
        try:
            result = await es.init_elasticsearch("http://localhost:9200")
        finally:
            del sys.modules["elasticsearch"]
            es._es_client = None
            es._es_available = False

        assert result is True
        mock_client.indices.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_skips_create_when_index_exists(self):
        """Should not create the index when it already exists."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True

        mock_module = MagicMock()
        mock_module.AsyncElasticsearch.return_value = mock_client

        sys.modules["elasticsearch"] = mock_module
        try:
            result = await es.init_elasticsearch("http://localhost:9200")
        finally:
            del sys.modules["elasticsearch"]
            es._es_client = None
            es._es_available = False

        assert result is True
        mock_client.indices.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_init_exception_path(self):
        """Should return False when initialization raises unexpectedly."""
        mock_client = AsyncMock()
        mock_client.ping.side_effect = RuntimeError("connection refused")

        mock_module = MagicMock()
        mock_module.AsyncElasticsearch.return_value = mock_client

        sys.modules["elasticsearch"] = mock_module
        try:
            result = await es.init_elasticsearch("http://localhost:9200")
        finally:
            del sys.modules["elasticsearch"]
            es._es_client = None
            es._es_available = False

        assert result is False
        assert es.is_available() is False


class TestIndexJobErrorPath:
    """Tests for the index_job error branch."""

    @pytest.mark.asyncio
    async def test_index_job_error_returns_false(self):
        """Should return False and log when indexing raises."""
        mock_client = AsyncMock()
        mock_client.index.side_effect = RuntimeError("es down")
        es._es_client = mock_client
        es._es_available = True

        try:
            result = await es.index_job({"id": "1", "title": "Security Engineer"})
        finally:
            es._es_client = None
            es._es_available = False

        assert result is False


class TestIndexJobsSuccessPath:
    """Tests for the successful bulk index path."""

    @pytest.mark.asyncio
    async def test_bulk_index_success_returns_count(self):
        """Should return the number of successfully indexed jobs."""
        mock_client = AsyncMock()
        es._es_client = mock_client
        es._es_available = True

        fake_helpers = types.ModuleType("elasticsearch.helpers")
        fake_helpers.async_bulk = AsyncMock(return_value=(2, []))  # type: ignore[attr-defined]
        fake_es = types.ModuleType("elasticsearch")
        fake_es.helpers = fake_helpers  # type: ignore[attr-defined]
        sys.modules["elasticsearch"] = fake_es
        sys.modules["elasticsearch.helpers"] = fake_helpers
        try:
            result = await es.index_jobs(
                [{"id": "1", "title": "A"}, {"source_id": "2", "title": "B"}]
            )
        finally:
            del sys.modules["elasticsearch"]
            del sys.modules["elasticsearch.helpers"]
            es._es_client = None
            es._es_available = False

        assert result == 2

    @pytest.mark.asyncio
    async def test_bulk_index_empty_actions_returns_zero(self):
        """Should return 0 when no job has an id (actions list empty)."""
        mock_client = AsyncMock()
        es._es_client = mock_client
        es._es_available = True

        fake_helpers = types.ModuleType("elasticsearch.helpers")
        fake_helpers.async_bulk = AsyncMock()  # type: ignore[attr-defined]
        fake_es = types.ModuleType("elasticsearch")
        fake_es.helpers = fake_helpers  # type: ignore[attr-defined]
        sys.modules["elasticsearch"] = fake_es
        sys.modules["elasticsearch.helpers"] = fake_helpers
        try:
            result = await es.index_jobs([{"title": "no id"}, {"title": "also none"}])
        finally:
            del sys.modules["elasticsearch"]
            del sys.modules["elasticsearch.helpers"]
            es._es_client = None
            es._es_available = False

        assert result == 0
        fake_helpers.async_bulk.assert_not_awaited()


class TestSearchExtendedFilters:
    """Tests for search filters not yet covered by the base suite."""

    @pytest.mark.asyncio
    async def test_search_with_location_job_type_experience(self):
        """Should build filters for location, job_type and experience_level."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response
        es._es_client = mock_client
        es._es_available = True

        try:
            await es.search_jobs(
                location="Remote",
                job_type="full_time",
                experience_level="senior",
            )
        finally:
            es._es_client = None
            es._es_available = False

        call_kwargs = mock_client.search.call_args.kwargs
        query = call_kwargs.get("query") or mock_client.search.call_args[1].get("query")
        filters = query["bool"]["filter"]
        assert {"match": {"location": "Remote"}} in filters
        assert {"term": {"job_type": "full_time"}} in filters
        assert {"term": {"experience_level": "senior"}} in filters

    @pytest.mark.asyncio
    async def test_search_with_max_salary_only(self):
        """Should build a range filter with only lte when only max_salary given."""
        mock_response = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
        }
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_response
        es._es_client = mock_client
        es._es_available = True

        try:
            await es.search_jobs(max_salary=100000.0)
        finally:
            es._es_client = None
            es._es_available = False

        call_kwargs = mock_client.search.call_args.kwargs
        query = call_kwargs.get("query") or mock_client.search.call_args[1].get("query")
        filters = query["bool"]["filter"]
        assert {"range": {"salary_min": {"lte": 100000.0}}} in filters


class TestDeleteAndStatsErrorPaths:
    """Tests for delete_job and get_index_stats error branches."""

    @pytest.mark.asyncio
    async def test_delete_job_error_returns_false(self):
        """Should return False when deletion raises."""
        mock_client = AsyncMock()
        mock_client.delete.side_effect = RuntimeError("es down")
        es._es_client = mock_client
        es._es_available = True

        try:
            result = await es.delete_job("1")
        finally:
            es._es_client = None
            es._es_available = False

        assert result is False

    @pytest.mark.asyncio
    async def test_get_index_stats_error_returns_minus_one(self):
        """Should return -1 document count when stats raise."""
        mock_client = AsyncMock()
        mock_client.indices.stats.side_effect = RuntimeError("es down")
        es._es_client = mock_client
        es._es_available = True

        try:
            result = await es.get_index_stats()
        finally:
            es._es_client = None
            es._es_available = False

        assert result == {
            "available": True,
            "index": es.INDEX_NAME,
            "document_count": -1,
        }
