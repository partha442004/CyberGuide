"""
Tests for API Endpoints

Tests for FastAPI routes.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_jobs(client: AsyncClient):
    """Test list jobs endpoint."""
    response = await client.get("/api/v1/jobs/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_search_jobs(client: AsyncClient):
    """Test search jobs endpoint."""
    response = await client.get("/api/v1/jobs/search", params={"q": "security"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_applications(client: AsyncClient):
    """Test list applications endpoint."""
    response = await client.get("/api/v1/applications/", params={"user_id": "test_user"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    """Test create user endpoint."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "securepass123",
    }
    response = await client.post("/api/v1/users/", json=user_data)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_notification_config(client: AsyncClient):
    """Test get notification config endpoint."""
    response = await client.get("/api/v1/notifications/config/test_user")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_skills_trending(client: AsyncClient):
    """Test trending skills endpoint."""
    response = await client.get("/api/v1/analytics/skills/trending")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_404_not_found(client: AsyncClient):
    """Test 404 handling."""
    response = await client.get("/api/v1/jobs/nonexistent_id")
    assert response.status_code == 404
