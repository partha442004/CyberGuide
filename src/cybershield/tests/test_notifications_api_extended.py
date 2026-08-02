"""
Extended tests for the Notifications API Router.

Focuses on the update_notification_config create-new path (no existing
config row) and the get_config default path when nothing exists.
"""

import pytest
from httpx import AsyncClient


class TestNotificationConfigExtended:
    @pytest.mark.asyncio
    async def test_update_creates_new_config(self, client: AsyncClient):
        """PUT /config/{user_id} with no existing row creates one."""
        response = await client.put(
            "/api/v1/notifications/config/user-new",
            json={
                "telegram_enabled": True,
                "daily_digest": False,
                "weekly_report": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["telegram_enabled"] is True
        assert data["daily_digest"] is False

    @pytest.mark.asyncio
    async def test_get_config_defaults_without_db_row(self, client: AsyncClient):
        """GET /config/{user_id} with no row returns default flags."""
        response = await client.get("/api/v1/notifications/config/user-none")
        assert response.status_code == 200
        data = response.json()
        assert data["email_enabled"] is True
        assert data["telegram_enabled"] is False
        assert data["instant_alerts"] is True

    @pytest.mark.asyncio
    async def test_update_then_get_roundtrip(self, client: AsyncClient):
        """Creating a config via PUT is then readable via GET."""
        await client.put(
            "/api/v1/notifications/config/user-rt",
            json={"slack_enabled": True, "scam_alerts": False},
        )
        response = await client.get("/api/v1/notifications/config/user-rt")
        assert response.status_code == 200
        data = response.json()
        assert data["slack_enabled"] is True
        assert data["scam_alerts"] is False

    @pytest.mark.asyncio
    async def test_send_notification_with_channel(self, client: AsyncClient):
        """POST /send echoes the channel and reports success."""
        response = await client.post(
            "/api/v1/notifications/send",
            json={"channel": "email", "message": "hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "email"
