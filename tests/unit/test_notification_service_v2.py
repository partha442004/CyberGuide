"""Unit tests for services/notification_service.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.domain.exceptions import NotificationError
from interntrack.services.notification_service import (
    DiscordChannel,
    EmailChannel,
    NotificationChannel,
    NotificationManager,
    SlackChannel,
    TelegramChannel,
)


class TestNotificationChannelABC:
    """Tests for NotificationChannel abstract base class."""

    # Note: the ABC enforcement tests (cannot_instantiate_directly /
    # subclass_must_implement_send) from the remote line were dropped during
    # the merge — our NotificationChannel is a plain base class with a raising
    # send() rather than abc.ABC, so those two assertions don't apply.
    def test_subclass_with_send_works(self):
        class CompleteChannel(NotificationChannel):
            async def send(self, message, subject=None):
                return True

        channel = CompleteChannel()
        assert channel is not None


class TestTelegramChannel:
    """Tests for TelegramChannel."""

    @pytest.fixture
    def channel(self):
        return TelegramChannel(bot_token="test-token", chat_id="12345")  # noqa: S106

    @pytest.mark.asyncio
    async def test_send_success(self, channel):
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            result = await channel.send("Hello World")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_with_apply_buttons(self, channel):
        """Inline keyboard buttons (label + url) ride in reply_markup."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            buttons = [("✅ Apply — Security Engineer", "https://x/apply")]
            result = await channel.send("Job digest", buttons=buttons)

            assert result is True
            _, kwargs = mock_client.post.call_args
            payload = kwargs["json"]
            assert payload["reply_markup"]["inline_keyboard"] == [
                [{"text": "✅ Apply — Security Engineer", "url": "https://x/apply"}]
            ]

    @pytest.mark.asyncio
    async def test_send_failure(self, channel):
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection failed")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            with pytest.raises(NotificationError):
                await channel.send("Hello World")


class TestDiscordChannel:
    """Tests for DiscordChannel."""

    @pytest.fixture
    def channel(self):
        return DiscordChannel(webhook_url="https://discord.com/api/webhooks/test")

    @pytest.mark.asyncio
    async def test_send_success_200(self, channel):
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            result = await channel.send("Hello")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_success_204(self, channel):
        mock_response = AsyncMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            result = await channel.send("Hello")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self, channel):
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            with pytest.raises(NotificationError):
                await channel.send("Hello")


class TestSlackChannel:
    """Tests for SlackChannel."""

    @pytest.fixture
    def channel(self):
        return SlackChannel(webhook_url="https://hooks.slack.com/test")

    @pytest.mark.asyncio
    async def test_send_success(self, channel):
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            result = await channel.send("Hello")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self, channel):
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            with pytest.raises(NotificationError):
                await channel.send("Hello")


class TestEmailChannel:
    """Tests for EmailChannel."""

    @pytest.fixture
    def channel(self):
        return EmailChannel(
            host="smtp.gmail.com",
            port=587,
            user="test@gmail.com",
            password="password",  # noqa: S106
            from_email="test@gmail.com",
        )

    @pytest.mark.asyncio
    async def test_send_success(self, channel):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = await channel.send("Hello", subject="Test")

            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_failure(self, channel):
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("Connection refused")

            with pytest.raises(NotificationError):
                await channel.send("Hello")


class TestNotificationManager:
    """Tests for NotificationManager."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def manager(self, mock_session):
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_phone_number = None
            return NotificationManager(mock_session)

    def test_init_no_channels(self, manager):
        assert manager.get_configured_channels() == []

    def test_get_configured_channels(self, manager):
        manager._channels["telegram"] = MagicMock()
        manager._channels["email"] = MagicMock()
        result = manager.get_configured_channels()
        assert "telegram" in result
        assert "email" in result

    @pytest.mark.asyncio
    async def test_notify_unconfigured_channel(self, manager):
        result = await manager.notify(["telegram"], "Hello")
        assert result["telegram"] is False

    @pytest.mark.asyncio
    async def test_notify_configured_channel(self, manager):
        mock_channel = AsyncMock()
        mock_channel.send.return_value = True
        manager._channels["telegram"] = mock_channel

        result = await manager.notify(["telegram"], "Hello", subject="Test")

        assert result["telegram"] is True
        mock_channel.send.assert_called_once_with("Hello", "Test", None)

    @pytest.mark.asyncio
    async def test_notify_passes_buttons_to_channel(self, manager):
        """Inline Apply buttons are forwarded to the channel send call."""
        mock_channel = AsyncMock()
        mock_channel.send.return_value = True
        manager._channels["telegram"] = mock_channel

        buttons = [("Apply", "https://example.com/job")]
        result = await manager.notify(
            ["telegram"],
            "Hello",
            subject="Test",
            buttons=buttons,
        )

        assert result["telegram"] is True
        mock_channel.send.assert_called_once_with("Hello", "Test", buttons)

    @pytest.mark.asyncio
    async def test_notify_channel_exception(self, manager):
        mock_channel = AsyncMock()
        mock_channel.send.side_effect = Exception("Failed")
        manager._channels["telegram"] = mock_channel

        result = await manager.notify(["telegram"], "Hello")

        assert result["telegram"] is False

    @pytest.mark.asyncio
    async def test_notify_all(self, manager):
        mock_channel1 = AsyncMock()
        mock_channel1.send.return_value = True
        mock_channel2 = AsyncMock()
        mock_channel2.send.return_value = True

        manager._channels["telegram"] = mock_channel1
        manager._channels["email"] = mock_channel2

        result = await manager.notify_all("Hello")

        assert result["telegram"] is True
        assert result["email"] is True

    def test_setup_channels_with_config(self, mock_session):
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = "token"
            mock_settings.telegram_chat_id = "chat_id"
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None

            mgr = NotificationManager(mock_session)
            assert "telegram" in mgr.get_configured_channels()
