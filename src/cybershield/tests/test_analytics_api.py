"""
Tests for the Analytics API Router.

Uses a fake repository override to exercise all analytics endpoints.
"""

import pytest
from httpx import AsyncClient

from cybershield.dependencies import get_company_repository, get_skill_repository
from cybershield.main import app


class _Skill(dict):
    """Dict-like skill object: attribute access (.name) + JSON serializable."""

    def __init__(self, name: str):
        super().__init__(name=name, category="general")
        self.name = name


class _FakeSkillRepo:
    async def get_trending_skills(self, days=30, limit=10):
        return [{"skill": _Skill("Python"), "job_count": 42}]

    async def get_skill_market_data(self):
        return [{"skill": _Skill("Python"), "demand_count": 9}]

    async def get_skill_trends(self, skill_id, months=12):
        return [{"period": "2024-01", "demand": 10}]


class _FakeCompanyRepo:
    async def get_top_hiring_companies(self, limit=10, country=None):
        return [{"name": "Acme", "job_count": 5}]


@pytest.fixture
def analytics_client(client: AsyncClient):
    """Client with fake analytics repos wired in."""

    async def override_skill():
        yield _FakeSkillRepo()

    async def override_company():
        yield _FakeCompanyRepo()

    app.dependency_overrides[get_skill_repository] = override_skill
    app.dependency_overrides[get_company_repository] = override_company
    yield client
    app.dependency_overrides.clear()


class TestAnalytics:
    @pytest.mark.asyncio
    async def test_trending_skills(self, analytics_client: AsyncClient):
        response = await analytics_client.get("/api/v1/analytics/skills/trending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["skill"]["name"] == "Python"

    @pytest.mark.asyncio
    async def test_skill_market_data(self, analytics_client: AsyncClient):
        response = await analytics_client.get("/api/v1/analytics/skills/market")
        assert response.status_code == 200
        assert response.json()[0]["skill"]["name"] == "Python"

    @pytest.mark.asyncio
    async def test_skill_trends(self, analytics_client: AsyncClient):
        response = await analytics_client.get("/api/v1/analytics/skills/skill-1/trends")
        assert response.status_code == 200
        assert response.json()[0]["period"] == "2024-01"

    @pytest.mark.asyncio
    async def test_top_hiring_companies(self, analytics_client: AsyncClient):
        response = await analytics_client.get("/api/v1/analytics/companies/top-hiring")
        assert response.status_code == 200
        assert response.json()[0]["name"] == "Acme"

    @pytest.mark.asyncio
    async def test_market_insights(self, analytics_client: AsyncClient):
        response = await analytics_client.get("/api/v1/analytics/insights/market")
        assert response.status_code == 200
        data = response.json()
        assert data["total_skills_tracked"] == 1
        assert data["top_demanding_skills"] == ["Python"]
        assert data["trending_skills"] == ["Python"]
        assert data["market_health"] == "active"

    @pytest.mark.asyncio
    async def test_trending_skills_validates_days(self, analytics_client: AsyncClient):
        response = await analytics_client.get(
            "/api/v1/analytics/skills/trending", params={"days": 1}
        )
        assert response.status_code == 422
