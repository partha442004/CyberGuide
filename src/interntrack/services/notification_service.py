"""
Notification service for multi-channel notifications.
"""

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.config import get_settings
from interntrack.domain.exceptions import NotificationError

settings = get_settings()


class NotificationChannel(ABC):
    """Base notification channel interface."""

    @abstractmethod
    async def send(self, message: str, subject: str | None = None) -> bool:
        """Send a notification. Must be implemented by subclasses."""
        ...


class TelegramChannel(NotificationChannel):
    """Telegram notification channel."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, message: str, subject: str | None = None) -> bool:
        """Send Telegram message."""
        try:
            import httpx

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)
                return response.status_code == 200
        except Exception as e:
            raise NotificationError("telegram", str(e))


class EmailChannel(NotificationChannel):
    """Email notification channel via SMTP."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_email: str,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email

    async def send(self, message: str, subject: str = "InternTrack") -> bool:
        """Send email notification."""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "html"))

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            raise NotificationError("email", str(e))


class DiscordChannel(NotificationChannel):
    """Discord webhook notification channel."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: str, subject: str | None = None) -> bool:
        """Send Discord webhook message."""
        try:
            import httpx

            payload = {"content": message}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10,
                )
                return response.status_code in (200, 204)
        except Exception as e:
            raise NotificationError("discord", str(e))


class SlackChannel(NotificationChannel):
    """Slack webhook notification channel."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: str, subject: str | None = None) -> bool:
        """Send Slack webhook message."""
        try:
            import httpx

            payload = {"text": message}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10,
                )
                return response.status_code == 200
        except Exception as e:
            raise NotificationError("slack", str(e))


class NotificationManager:
    """Notification manager for multi-channel delivery."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._channels: dict[str, NotificationChannel] = {}
        self._setup_channels()

    def _setup_channels(self) -> None:
        """Setup configured notification channels."""
        if settings.telegram_bot_token and settings.telegram_chat_id:
            self._channels["telegram"] = TelegramChannel(
                settings.telegram_bot_token,
                settings.telegram_chat_id,
            )

        if settings.smtp_user and settings.smtp_password:
            self._channels["email"] = EmailChannel(
                settings.smtp_host,
                settings.smtp_port,
                settings.smtp_user,
                settings.smtp_password,
                settings.email_from,
            )

        if settings.discord_webhook_url:
            self._channels["discord"] = DiscordChannel(settings.discord_webhook_url)

        if settings.slack_webhook_url:
            self._channels["slack"] = SlackChannel(settings.slack_webhook_url)

    async def notify(
        self,
        channels: list[str],
        message: str,
        subject: str | None = None,
    ) -> dict[str, bool]:
        """Send notification to multiple channels."""
        results = {}
        for channel_name in channels:
            channel = self._channels.get(channel_name)
            if channel:
                try:
                    results[channel_name] = await channel.send(message, subject)
                except Exception:
                    results[channel_name] = False
            else:
                results[channel_name] = False
        return results

    async def notify_all(
        self, message: str, subject: str | None = None
    ) -> dict[str, bool]:
        """Send notification to all configured channels."""
        return await self.notify(list(self._channels.keys()), message, subject)

    def get_configured_channels(self) -> list[str]:
        """Get list of configured channels."""
        return list(self._channels.keys())
