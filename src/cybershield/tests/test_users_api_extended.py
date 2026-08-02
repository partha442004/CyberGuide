"""
Extended tests for the Users API Router.

Covers get_user (found + 404), create_user (password hashing + missing
password), update_user, and the watchlist endpoints' error paths.
"""

import pytest
from httpx import AsyncClient

from cybershield.repositories.user_repository import UserRepository


async def _create_user(client: AsyncClient, **overrides) -> str:
    """Create a user and return the id."""
    data = {
        "username": "ext_user",
        "email": "ext@example.com",
        "full_name": "Ext Tester",
        "password": "testpass123",
        **overrides,
    }
    response = await client.post("/api/v1/users/", json=data)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


class TestGetUser:
    @pytest.mark.asyncio
    async def test_get_existing_user(self, client: AsyncClient):
        user_id = await _create_user(client, username="getter")
        response = await client.get(f"/api/v1/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "getter"
        assert data["email"] == "ext@example.com"
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_get_missing_user_404(self, client: AsyncClient):
        response = await client.get("/api/v1/users/nonexistent-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_user_hashes_password(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/users/",
            json={
                "username": "hashme",
                "email": "hash@example.com",
                "password": "secret123",
                "target_roles": ["Security Analyst"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "hashme"
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_create_user_empty_password_sets_empty_hash(self, client: AsyncClient):
        """Direct route call with a falsy password hits the else branch."""

        from cybershield.api.v1.users import create_user
        from cybershield.schemas.user import UserCreate

        class _StubUser:
            id = "u-1"
            username = "nopass"
            email = "nopass@example.com"
            is_active = True
            is_verified = False
            created_at = None
            updated_at = None
            full_name = None
            phone = None
            location = None
            country = None
            bio = None
            linkedin_url = None
            github_url = None
            portfolio_url = None

        captured = {}

        class _Repo(UserRepository):
            def __init__(self) -> None:
                super().__init__(None)  # type: ignore[arg-type]

            async def create(self, data):
                captured["data"] = dict(data)
                return _StubUser()

        # model_construct bypasses the min_length=6 validation so we can
        # exercise the falsy-password else branch of the route.
        payload = UserCreate.model_construct(
            username="nopass",
            email="nopass@example.com",
            password="",
        )
        user = await create_user(payload, _Repo())
        assert user.username == "nopass"
        assert captured["data"]["hashed_password"] == ""


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_user(self, client: AsyncClient):
        user_id = await _create_user(client, username="updater")
        response = await client.put(
            f"/api/v1/users/{user_id}",
            json={"full_name": "Updated Name", "bio": "new bio"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"


class TestWatchlistErrors:
    @pytest.mark.asyncio
    async def test_duplicate_company_watchlist_400(self, client: AsyncClient):
        user_id = await _create_user(client, username="dupco")
        await client.post(
            f"/api/v1/users/{user_id}/company-watchlist",
            json={"company_id": "acme-1"},
        )
        response = await client.post(
            f"/api/v1/users/{user_id}/company-watchlist",
            json={"company_id": "acme-1"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_keyword_watchlist_400(self, client: AsyncClient):
        user_id = await _create_user(client, username="dupkw")
        await client.post(
            f"/api/v1/users/{user_id}/keyword-watchlist",
            json={"keyword": "splunk"},
        )
        response = await client.post(
            f"/api/v1/users/{user_id}/keyword-watchlist",
            json={"keyword": "splunk"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_remove_missing_company_watchlist_404(self, client: AsyncClient):
        user_id = await _create_user(client, username="rmco")
        response = await client.delete(f"/api/v1/users/{user_id}/company-watchlist/missing")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_missing_keyword_watchlist_404(self, client: AsyncClient):
        user_id = await _create_user(client, username="rmkw")
        response = await client.delete(f"/api/v1/users/{user_id}/keyword-watchlist/missing")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_watchlists_empty(self, client: AsyncClient):
        user_id = await _create_user(client, username="emptywl")
        company = await client.get(f"/api/v1/users/{user_id}/company-watchlist")
        keyword = await client.get(f"/api/v1/users/{user_id}/keyword-watchlist")
        assert company.status_code == 200
        assert company.json() == []
        assert keyword.status_code == 200
        assert keyword.json() == []
