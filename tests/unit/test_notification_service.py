"""Unit tests for services/notification_service.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestNotificationChannel:
    """Tests for base NotificationChannel class."""

    def test_base_cannot_be_instantiated(self):
        from abc import ABC
        from interntrack.services.notification_service import NotificationChannel

        assert issubclass(NotificationChannel, ABC)
        with pytest.raises(TypeError):
            NotificationChannel()

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        from interntrack.domain.exceptions import NotificationError
        from interntrack.services.notification_service import TelegramChannel

        channel = TelegramChannel("token123", "chat456")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

            with pytest.raises(NotificationError):
                await channel.send("Hello World")


class TestEmailChannel:
    """Tests for EmailChannel class."""

    def test_init(self):
        from interntrack.services.notification_service import EmailChannel

        channel = EmailChannel("smtp.gmail.com", 587, "user", "pass", "from@test.com")
        assert channel.host == "smtp.gmail.com"
        assert channel.port == 587
        assert channel.user == "user"
        assert channel.password == "pass"
        assert channel.from_email == "from@test.com"

    @pytest.mark.asyncio
    async def test_send_success(self):
        from interntrack.services.notification_service import EmailChannel

        channel = EmailChannel("smtp.gmail.com", 587, "user", "pass", "from@test.com")

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = await channel.send("<p>Hello</p>", subject="Test")

            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user", "pass")

    @pytest.mark.asyncio
    async def test_send_failure(self):
        from interntrack.domain.exceptions import NotificationError
        from interntrack.services.notification_service import EmailChannel

        channel = EmailChannel("smtp.gmail.com", 587, "user", "pass", "from@test.com")

        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__ = MagicMock(side_effect=Exception("SMTP error"))
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(NotificationError):
                await channel.send("<p>Hello</p>")


class TestDiscordChannel:
    """Tests for DiscordChannel class."""

    def test_init(self):
        from interntrack.services.notification_service import DiscordChannel

        channel = DiscordChannel("https://discord.com/api/webhooks/123/abc")
        assert channel.webhook_url == "https://discord.com/api/webhooks/123/abc"

    @pytest.mark.asyncio
    async def test_send_success(self):
        from interntrack.services.notification_service import DiscordChannel

        channel = DiscordChannel("https://discord.com/api/webhooks/123/abc")

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await channel.send("Hello Discord")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        from interntrack.domain.exceptions import NotificationError
        from interntrack.services.notification_service import DiscordChannel

        channel = DiscordChannel("https://discord.com/api/webhooks/123/abc")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("Timeout"))

            with pytest.raises(NotificationError):
                await channel.send("Hello Discord")


class TestSlackChannel:
    """Tests for SlackChannel class."""

    def test_init(self):
        from interntrack.services.notification_service import SlackChannel

        channel = SlackChannel("https://hooks.slack.com/services/xxx")
        assert channel.webhook_url == "https://hooks.slack.com/services/xxx"

    @pytest.mark.asyncio
    async def test_send_success(self):
        from interntrack.services.notification_service import SlackChannel

        channel = SlackChannel("https://hooks.slack.com/services/xxx")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await channel.send("Hello Slack")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        from interntrack.domain.exceptions import NotificationError
        from interntrack.services.notification_service import SlackChannel

        channel = SlackChannel("https://hooks.slack.com/services/xxx")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("Network error"))

            with pytest.raises(NotificationError):
                await channel.send("Hello Slack")


class TestNotificationManager:
    """Tests for NotificationManager class."""

    @patch("interntrack.services.notification_service.settings")
    def test_init_no_channels(self, mock_settings):
        from interntrack.services.notification_service import NotificationManager

        mock_settings.telegram_bot_token = None
        mock_settings.telegram_chat_id = None
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.discord_webhook_url = None
        mock_settings.slack_webhook_url = None

        session = AsyncMock()
        manager = NotificationManager(session)

        assert manager.get_configured_channels() == []

    @patch("interntrack.services.notification_service.settings")
    def test_init_with_telegram(self, mock_settings):
        from interntrack.services.notification_service import NotificationManager

        mock_settings.telegram_bot_token = "token"
        mock_settings.telegram_chat_id = "chat_id"
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.discord_webhook_url = None
        mock_settings.slack_webhook_url = None

        session = AsyncMock()
        manager = NotificationManager(session)

        assert "telegram" in manager.get_configured_channels()

    @pytest.mark.asyncio
    @patch("interntrack.services.notification_service.settings")
    async def test_notify_specific_channels(self, mock_settings):
        from interntrack.services.notification_service import NotificationManager

        mock_settings.telegram_bot_token = "token"
        mock_settings.telegram_chat_id = "chat_id"
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.discord_webhook_url = None
        mock_settings.slack_webhook_url = None

        session = AsyncMock()
        manager = NotificationManager(session)

        # Mock the telegram channel
        mock_channel = AsyncMock()
        mock_channel.send.return_value = True
        manager._channels["telegram"] = mock_channel

        results = await manager.notify(["telegram"], "Test message")

        assert results == {"telegram": True}
        mock_channel.send.assert_called_once_with("Test message", None)

    @pytest.mark.asyncio
    @patch("interntrack.services.notification_service.settings")
    async def test_notify_unknown_channel(self, mock_settings):
        from interntrack.services.notification_service import NotificationManager

        mock_settings.telegram_bot_token = None
        mock_settings.telegram_chat_id = None
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.discord_webhook_url = None
        mock_settings.slack_webhook_url = None

        session = AsyncMock()
        manager = NotificationManager(session)

        results = await manager.notify(["unknown"], "Test message")

        assert results == {"unknown": False}

    @pytest.mark.asyncio
    @patch("interntrack.services.notification_service.settings")
    async def test_notify_all(self, mock_settings):
        from interntrack.services.notification_service import NotificationManager

        mock_settings.telegram_bot_token = "token"
        mock_settings.telegram_chat_id = "chat_id"
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None
        mock_settings.discord_webhook_url = None
        mock_settings.slack_webhook_url = None

        session = AsyncMock()
        manager = NotificationManager(session)

        # Mock the telegram channel
        mock_channel = AsyncMock()
        mock_channel.send.return_value = True
        manager._channels["telegram"] = mock_channel

        results = await manager.notify_all("Test message")

        assert "telegram" in results
        assert results["telegram"] is True
