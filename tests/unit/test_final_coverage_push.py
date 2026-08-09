"""Final coverage push: tests for notification service and worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Notification Service ──────────────────────────────────────────────────


class TestNotificationServiceExtended:
    """Extended tests for notification_service.py."""

    def test_notification_manager_init(self):
        from interntrack.services.notification_service import NotificationManager

        session = AsyncMock()
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
            manager = NotificationManager(session)
        assert manager.get_configured_channels() == []

    def test_notification_manager_with_channels(self):
        from interntrack.services.notification_service import NotificationManager

        session = AsyncMock()
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = "token"
            mock_settings.telegram_chat_id = "123"
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = "https://discord.com/webhook"
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        channels = manager.get_configured_channels()
        assert "telegram" in channels
        assert "discord" in channels

    @pytest.mark.asyncio
    async def test_notify_channel_not_configured(self):
        from interntrack.services.notification_service import NotificationManager

        session = AsyncMock()
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        results = await manager.notify(["email"], "test message")
        assert results["email"] is False

    @pytest.mark.asyncio
    async def test_notify_channel_success(self):
        from interntrack.services.notification_service import NotificationManager

        session = AsyncMock()
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)
        manager._channels["test"] = mock_channel

        results = await manager.notify(["test"], "hello")
        assert results["test"] is True

    @pytest.mark.asyncio
    async def test_notify_channel_exception(self):
        from interntrack.services.notification_service import NotificationManager

        session = AsyncMock()
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(side_effect=Exception("Error"))
        manager._channels["test"] = mock_channel

        results = await manager.notify(["test"], "hello")
        assert results["test"] is False

    @pytest.mark.asyncio
    async def test_notify_all(self):
        from interntrack.services.notification_service import NotificationManager

        session = AsyncMock()
        with patch(
            "interntrack.services.notification_service.settings",
        ) as mock_settings:
            mock_settings.telegram_bot_token = None
            mock_settings.telegram_chat_id = None
            mock_settings.smtp_user = None
            mock_settings.smtp_password = None
            mock_settings.discord_webhook_url = None
            mock_settings.slack_webhook_url = None
            manager = NotificationManager(session)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)
        manager._channels["telegram"] = mock_channel

        results = await manager.notify_all("hello")
        assert "telegram" in results

    @pytest.mark.asyncio
    async def test_telegram_channel_send(self):
        from interntrack.services.notification_service import TelegramChannel

        channel = TelegramChannel("token", "123")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await channel.send("Hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_discord_channel_send(self):
        from interntrack.services.notification_service import DiscordChannel

        channel = DiscordChannel("https://discord.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await channel.send("Hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_slack_channel_send(self):
        from interntrack.services.notification_service import SlackChannel

        channel = SlackChannel("https://slack.com/webhook")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await channel.send("Hello")
        assert result is True


# ─── Worker ─────────────────────────────────────────────────────────────────


class TestWorkerExtended:
    """Extended tests for worker.py."""

    @pytest.mark.asyncio
    async def test_worker_main(self):
        from interntrack.worker import main

        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()

        with (
            patch("interntrack.worker.setup_logging"),
            patch("interntrack.worker.setup_scheduler", return_value=mock_scheduler),
            patch("interntrack.worker.signal"),
            patch("asyncio.sleep", side_effect=KeyboardInterrupt),
        ):
            await main()

        mock_scheduler.start.assert_called_once()
        mock_scheduler.shutdown.assert_called_once()
