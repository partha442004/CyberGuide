"""
Tests for Watchlist API Endpoints

Integration tests for company and keyword watchlist CRUD operations.
"""

import pytest
from httpx import AsyncClient


# Helper to create a test user and return its ID
async def create_test_user(client: AsyncClient) -> str:
    """Create a test user and return the user ID."""
    user_data = {
        "username": "watchlist_tester",
        "email": "watchlist@example.com",
        "full_name": "Watchlist Tester",
        "password": "testpass123",
    }
    response = await client.post("/api/v1/users/", json=user_data)
    assert response.status_code == 201
    return response.json()["id"]


# ==================== Company Watchlist Tests ====================

@pytest.mark.asyncio
async def test_add_company_watchlist(client: AsyncClient):
    """Test adding a company to watchlist."""
    user_id = await create_test_user(client)
    response = await client.post(
        f"/api/v1/users/{user_id}/company-watchlist",
        json={"company_id": "microsoft-id-123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["message"] == "Company added to watchlist"


@pytest.mark.asyncio
async def test_get_company_watchlist(client: AsyncClient):
    """Test getting company watchlist."""
    user_id = await create_test_user(client)
    # Add a company first
    await client.post(
        f"/api/v1/users/{user_id}/company-watchlist",
        json={"company_id": "google-id-456"},
    )
    # Get the watchlist
    response = await client.get(f"/api/v1/users/{user_id}/company-watchlist")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_add_duplicate_company_watchlist(client: AsyncClient):
    """Test adding duplicate company to watchlist returns 400."""
    user_id = await create_test_user(client)
    # Add company once
    await client.post(
        f"/api/v1/users/{user_id}/company-watchlist",
        json={"company_id": "amazon-id-789"},
    )
    # Try to add again - should fail
    response = await client.post(
        f"/api/v1/users/{user_id}/company-watchlist",
        json={"company_id": "amazon-id-789"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_remove_company_watchlist(client: AsyncClient):
    """Test removing a company from watchlist."""
    user_id = await create_test_user(client)
    # Add a company
    await client.post(
        f"/api/v1/users/{user_id}/company-watchlist",
        json={"company_id": "cisco-id-101"},
    )
    # Remove it
    response = await client.delete(
        f"/api/v1/users/{user_id}/company-watchlist/cisco-id-101"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Company removed from watchlist"


@pytest.mark.asyncio
async def test_remove_nonexistent_company_watchlist(client: AsyncClient):
    """Test removing non-existent company from watchlist returns 404."""
    user_id = await create_test_user(client)
    response = await client.delete(
        f"/api/v1/users/{user_id}/company-watchlist/nonexistent-id"
    )
    assert response.status_code == 404


# ==================== Keyword Watchlist Tests ====================

@pytest.mark.asyncio
async def test_add_keyword_watchlist(client: AsyncClient):
    """Test adding a keyword to watchlist."""
    user_id = await create_test_user(client)
    response = await client.post(
        f"/api/v1/users/{user_id}/keyword-watchlist",
        json={"keyword": "splunk", "category": "SIEM"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["message"] == "Keyword added to watchlist"


@pytest.mark.asyncio
async def test_get_keyword_watchlist(client: AsyncClient):
    """Test getting keyword watchlist."""
    user_id = await create_test_user(client)
    # Add a keyword first
    await client.post(
        f"/api/v1/users/{user_id}/keyword-watchlist",
        json={"keyword": "python", "category": "Programming"},
    )
    # Get the watchlist
    response = await client.get(f"/api/v1/users/{user_id}/keyword-watchlist")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_add_duplicate_keyword_watchlist(client: AsyncClient):
    """Test adding duplicate keyword to watchlist returns 400."""
    user_id = await create_test_user(client)
    # Add keyword once
    await client.post(
        f"/api/v1/users/{user_id}/keyword-watchlist",
        json={"keyword": "aws"},
    )
    # Try to add again - should fail
    response = await client.post(
        f"/api/v1/users/{user_id}/keyword-watchlist",
        json={"keyword": "aws"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_remove_keyword_watchlist(client: AsyncClient):
    """Test removing a keyword from watchlist."""
    user_id = await create_test_user(client)
    # Add a keyword
    await client.post(
        f"/api/v1/users/{user_id}/keyword-watchlist",
        json={"keyword": "sentinel"},
    )
    # Remove it
    response = await client.delete(
        f"/api/v1/users/{user_id}/keyword-watchlist/sentinel"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Keyword removed from watchlist"


@pytest.mark.asyncio
async def test_remove_nonexistent_keyword_watchlist(client: AsyncClient):
    """Test removing non-existent keyword from watchlist returns 404."""
    user_id = await create_test_user(client)
    response = await client.delete(
        f"/api/v1/users/{user_id}/keyword-watchlist/nonexistent"
    )
    assert response.status_code == 404


# ==================== Cross-Type Watchlist Tests ====================

@pytest.mark.asyncio
async def test_company_and_keyword_watchlists_independent(client: AsyncClient):
    """Test company and keyword watchlists are independent."""
    user_id = await create_test_user(client)
    # Add company
    await client.post(
        f"/api/v1/users/{user_id}/company-watchlist",
        json={"company_id": "microsoft"},
    )
    # Add keyword
    await client.post(
        f"/api/v1/users/{user_id}/keyword-watchlist",
        json={"keyword": "python"},
    )
    # Get company watchlist
    company_response = await client.get(f"/api/v1/users/{user_id}/company-watchlist")
    assert company_response.status_code == 200
    companies = company_response.json()
    assert len(companies) >= 1
    assert companies[0]["watch_type"] == "company"

    # Get keyword watchlist
    keyword_response = await client.get(f"/api/v1/users/{user_id}/keyword-watchlist")
    assert keyword_response.status_code == 200
    keywords = keyword_response.json()
    assert len(keywords) >= 1
    assert keywords[0]["watch_type"] == "keyword"
