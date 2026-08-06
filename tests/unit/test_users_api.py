"""
Tests for the users API — registration, login, profiles and auto-enabled alerts.
"""

import pytest


class TestRegisterUser:
    """POST /api/v1/users/register."""

    @pytest.mark.asyncio
    async def test_register_creates_profile_and_auto_enables_alerts(self, client):
        """A new account gets its own AlertPreferences with the chosen domains."""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "location": "London",
                "experience_level": "senior",
                "domains": ["security", "coding"],
                "skills": ["python", "burp suite", "nmap"],
                "telegram_chat_id": "12345",
            },
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Ada Lovelace"
        assert data["email"] == "ada@example.com"
        assert data["domains"] == ["security", "coding"]
        assert data["skills"] == ["python", "burp suite", "nmap"]
        assert data["experience_level"] == "senior"
        assert data["telegram_chat_id"] == "12345"
        assert data["id"]
        # The secret access token is returned once at signup.
        assert data.get("access_token")

        # Alerts auto-enabled with the chosen domains.
        prefs = await client.get(f"/api/v1/notifications/preferences/{data['id']}")
        assert prefs.status_code == 200
        pref_data = prefs.json()
        assert pref_data["is_enabled"] is True
        assert pref_data["domains"] == ["security", "coding"]
        assert pref_data["user_id"] == data["id"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email_conflict(self, client):
        await client.post(
            "/api/v1/users/register",
            json={"name": "One", "email": "dup@example.com"},
        )
        response = await client.post(
            "/api/v1/users/register",
            json={"name": "Two", "email": "DUP@example.com"},  # case-insensitive
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_invalid_email_rejected(self, client):
        response = await client.post(
            "/api/v1/users/register",
            json={"name": "X", "email": "not-an-email"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_unknown_domains_dropped(self, client):
        """Unknown domain keys are filtered out of the saved profile."""
        response = await client.post(
            "/api/v1/users/register",
            json={
                "name": "Filtered",
                "email": "filtered@example.com",
                "domains": ["security", "quantum-computing"],
            },
        )
        assert response.status_code == 201
        assert response.json()["domains"] == ["security"]

    @pytest.mark.asyncio
    async def test_register_invalid_experience_level(self, client):
        response = await client.post(
            "/api/v1/users/register",
            json={
                "name": "X",
                "email": "x@example.com",
                "experience_level": "boss",
            },
        )
        assert response.status_code == 422


class TestLoginUser:
    """POST /api/v1/users/login (email only)."""

    @pytest.mark.asyncio
    async def test_login_with_access_token_returns_profile(self, client):
        register = await client.post(
            "/api/v1/users/register",
            json={"name": "Grace", "email": "grace@example.com"},
        )
        assert register.status_code == 201
        token = register.json()["access_token"]
        assert token

        response = await client.post(
            "/api/v1/users/login",
            json={"email": "GRACE@example.com", "token": token},  # case-insensitive
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Grace"
        assert data["email"] == "grace@example.com"

    @pytest.mark.asyncio
    async def test_login_with_wrong_token_rejected(self, client):
        register = await client.post(
            "/api/v1/users/register",
            json={"name": "Token", "email": "token@example.com"},
        )
        assert register.status_code == 201
        response = await client.post(
            "/api/v1/users/login",
            json={"email": "token@example.com", "token": "wrong-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_email_404(self, client):
        response = await client.post(
            "/api/v1/users/login",
            json={"email": "nobody@example.com"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rotate_token_replaces_secret(self, client):
        register = await client.post(
            "/api/v1/users/register",
            json={"name": "Rotate", "email": "rotate@example.com"},
        )
        user_id = register.json()["id"]
        old_token = register.json()["access_token"]

        rotated = await client.post(f"/api/v1/users/{user_id}/rotate-token")
        assert rotated.status_code == 200
        new_token = rotated.json()["access_token"]
        assert new_token and new_token != old_token

        # The old token no longer works.
        old_login = await client.post(
            "/api/v1/users/login",
            json={"email": "rotate@example.com", "token": old_token},
        )
        assert old_login.status_code == 401
        new_login = await client.post(
            "/api/v1/users/login",
            json={"email": "rotate@example.com", "token": new_token},
        )
        assert new_login.status_code == 200


class TestUserProfile:
    """GET / PUT /api/v1/users/{user_id}."""

    async def _register(self, client, email="profile@example.com"):
        response = await client.post(
            "/api/v1/users/register",
            json={"name": "Profile", "email": email, "domains": ["data"]},
        )
        assert response.status_code == 201
        return response.json()

    @pytest.mark.asyncio
    async def test_get_user(self, client):
        user = await self._register(client)
        response = await client.get(f"/api/v1/users/{user['id']}")
        assert response.status_code == 200
        assert response.json()["email"] == user["email"]

    @pytest.mark.asyncio
    async def test_get_user_404(self, client):
        response = await client.get("/api/v1/users/does-not-exist")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_user(self, client):
        user = await self._register(client)
        response = await client.put(
            f"/api/v1/users/{user['id']}",
            json={
                "name": "Renamed",
                "domains": ["coding", "security"],
                "skills": ["react", "go"],
                "telegram_chat_id": "987",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed"
        assert data["domains"] == ["coding", "security"]
        assert data["skills"] == ["react", "go"]
        assert data["telegram_chat_id"] == "987"

    @pytest.mark.asyncio
    async def test_list_users(self, client):
        await self._register(client, email="list1@example.com")
        await self._register(client, email="list2@example.com")
        response = await client.get("/api/v1/users")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()["users"]]
        assert "list1@example.com" in emails
        assert "list2@example.com" in emails
