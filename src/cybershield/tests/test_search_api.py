"""
Tests for the Search API Router.

Mocks the elasticsearch service module to exercise the router's
parameter validation, sorting fallback, and response shaping.
"""

import pytest
from httpx import AsyncClient

from cybershield.api.v1 import search as search_module

SEARCH_URL = "/api/v1/search/"


class TestSearchJobs:
    @pytest.mark.asyncio
    async def test_search_passthrough(self, client: AsyncClient, monkeypatch):
        async def fake_search_jobs(**kwargs):
            assert kwargs["query"] == "security"
            return {
                "results": [{"id": "1", "title": "Security Analyst"}],
                "total": 1,
                "source": "elasticsearch",
                "aggregations": {"by_company": [{"key": "Acme", "count": 1}]},
            }

        monkeypatch.setattr(search_module.es, "search_jobs", fake_search_jobs)

        response = await client.get(SEARCH_URL, params={"q": "security"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["source"] == "elasticsearch"
        assert data["items"][0]["title"] == "Security Analyst"
        assert data["aggregations"]["by_company"] == [{"key": "Acme", "count": 1}]
        assert data["skip"] == 0
        assert data["limit"] == 20

    @pytest.mark.asyncio
    async def test_search_invalid_sort_falls_back_to_score(self, client: AsyncClient, monkeypatch):
        captured = {}

        async def fake_search_jobs(**kwargs):
            captured.update(kwargs)
            return {"results": [], "total": 0, "source": "database"}

        monkeypatch.setattr(search_module.es, "search_jobs", fake_search_jobs)

        response = await client.get(
            SEARCH_URL,
            params={"q": "aws", "sort_by": "not-a-valid-field", "sort_order": "weird"},
        )
        assert response.status_code == 200
        assert captured["sort_by"] == "_score"
        assert captured["sort_order"] == "desc"

    @pytest.mark.asyncio
    async def test_search_passes_all_filters(self, client: AsyncClient, monkeypatch):
        captured = {}

        async def fake_search_jobs(**kwargs):
            captured.update(kwargs)
            return {"results": [], "total": 0, "source": "database"}

        monkeypatch.setattr(search_module.es, "search_jobs", fake_search_jobs)

        response = await client.get(
            SEARCH_URL,
            params={
                "q": "python",
                "company": "Acme",
                "country": "India",
                "location": "Remote",
                "skills": ["python", "docker"],
                "job_type": "full_time",
                "experience_level": "mid",
                "is_remote": "true",
                "min_salary": "50000",
                "max_salary": "150000",
                "sort_by": "salary_min",
                "sort_order": "asc",
                "skip": "10",
                "limit": "5",
            },
        )
        assert response.status_code == 200
        assert captured["query"] == "python"
        assert captured["company"] == "Acme"
        assert captured["country"] == "India"
        assert captured["skills"] == ["python", "docker"]
        assert captured["job_type"] == "full_time"
        assert captured["is_remote"] is True
        assert captured["min_salary"] == 50000
        assert captured["sort_by"] == "salary_min"
        assert captured["sort_order"] == "asc"
        assert captured["skip"] == 10
        assert captured["limit"] == 5

    @pytest.mark.asyncio
    async def test_search_database_fallback_empty(self, client: AsyncClient, monkeypatch):
        async def fake_search_jobs(**kwargs):
            return {"results": [], "total": 0, "source": "database"}

        monkeypatch.setattr(search_module.es, "search_jobs", fake_search_jobs)

        response = await client.get(SEARCH_URL, params={"q": "nothing"})
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_search_validates_limit_range(self, client: AsyncClient, monkeypatch):
        async def fake_search_jobs(**kwargs):
            return {"results": [], "total": 0, "source": "database"}

        monkeypatch.setattr(search_module.es, "search_jobs", fake_search_jobs)

        # limit above 100 should be rejected by FastAPI validation
        response = await client.get(SEARCH_URL, params={"q": "x", "limit": 200})
        assert response.status_code == 422


class TestSearchStatus:
    @pytest.mark.asyncio
    async def test_status_available(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(search_module.es, "is_available", lambda: True)

        async def fake_stats():
            return {"available": True, "index": "cybershield_jobs", "document_count": 42}

        monkeypatch.setattr(search_module.es, "get_index_stats", fake_stats)

        response = await client.get("/api/v1/search/status")
        assert response.status_code == 200
        data = response.json()
        assert data["elasticsearch_available"] is True
        assert data["index_stats"]["document_count"] == 42

    @pytest.mark.asyncio
    async def test_status_unavailable(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(search_module.es, "is_available", lambda: False)

        async def fake_stats():
            return {"available": False}

        monkeypatch.setattr(search_module.es, "get_index_stats", fake_stats)

        response = await client.get("/api/v1/search/status")
        assert response.status_code == 200
        data = response.json()
        assert data["elasticsearch_available"] is False
        assert data["index_stats"]["available"] is False
