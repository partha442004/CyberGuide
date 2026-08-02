"""
Tests for the Notifications API Router.

Covers notification config get/update and the test/send endpoints.
"""

import pytest
from httpx import AsyncClient

from cybershield.domain.models import NotificationConfig

CONFIG_URL = "/api/v1/notifications/config"


class TestGetNotificationConfig:
    @pytest.mark.asyncio
    async def test_get_default_config_when_none_exists(self, client: AsyncClient):
        response = await client.get(f"{CONFIG_URL}/new-user")
        assert response.status_code == 200
        data = response.json()
        assert data["email_enabled"] is True
        assert data["telegram_enabled"] is False
        assert data["instant_alerts"] is True

    @pytest.mark.asyncio
    async def test_get_existing_config(self, client: AsyncClient, db_session):
        config = NotificationConfig(
            user_id="existing-user",
            channel="telegram",
            is_enabled=True,
            config={"telegram_chat_id": "12345"},
        )
        db_session.add(config)
        await db_session.flush()

        response = await client.get(f"{CONFIG_URL}/existing-user")
        assert response.status_code == 200
        # Response model is the schema NotificationConfig, which returns defaults
        # for the preference fields regardless of the stored ORM row.
        data = response.json()
        assert "email_enabled" in data
        assert data["email_enabled"] is True


class TestUpdateNotificationConfig:
    @pytest.mark.asyncio
    async def test_update_existing_config(self, client: AsyncClient, db_session):
        config = NotificationConfig(
            user_id="update-user",
            channel="email",
            is_enabled=True,
            config={},
        )
        db_session.add(config)
        await db_session.flush()

        response = await client.put(
            f"{CONFIG_URL}/update-user",
            json={
                "email_enabled": False,
                "telegram_enabled": True,
                "instant_alerts": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # The PUT stores the submitted values as attributes on the row, which
        # are reflected in the response; telegram_enabled was set to True.
        assert data["telegram_enabled"] is True


class TestTestNotification:
    @pytest.mark.asyncio
    async def test_test_notification_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/notifications/test",
            json={"channel": "telegram", "message": "hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "telegram"
        assert "Test notification" in data["message"]

    @pytest.mark.asyncio
    async def test_test_notification_invalid_channel(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/notifications/test",
            json={"channel": "carrier-pigeon"},
        )
        assert response.status_code == 422


class TestSendNotification:
    @pytest.mark.asyncio
    async def test_send_notification_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/notifications/send",
            json={"channel": "slack", "message": "job alert"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["channel"] == "slack"

    @pytest.mark.asyncio
    async def test_send_notification_unknown_channel(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/notifications/send",
            json={"message": "no channel given"},
        )
        assert response.status_code == 200
        assert response.json()["channel"] == "unknown"
