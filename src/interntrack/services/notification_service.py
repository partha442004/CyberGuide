"""
Notification service for multi-channel notifications.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.config import get_settings
from interntrack.domain.exceptions import NotificationError
from interntrack.metrics import business_metrics_store

settings = get_settings()


class NotificationChannel:
    """Base notification channel interface."""

    async def send(
        self,
        message: str,
        subject: str | None = None,  # noqa: ARG002 (interface)
        buttons: list[tuple[str, str]] | None = None,  # noqa: ARG002
    ) -> bool:
        raise NotImplementedError


class TelegramChannel(NotificationChannel):
    """Telegram notification channel."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(
        self,
        message: str,
        subject: str | None = None,  # noqa: ARG002 (interface)
        buttons: list[tuple[str, str]] | None = None,
    ) -> bool:
        """Send Telegram message, optionally with inline Apply buttons.

        ``buttons`` is a list of ``(label, url)`` pairs; each pair becomes an
        inline keyboard button that opens the URL when tapped.
        """
        try:
            import httpx

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload: dict = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            if buttons:
                # One button per row, up to Telegram's 100-button limit.
                inline = [[{"text": label, "url": link}] for label, link in buttons]
                payload["reply_markup"] = {"inline_keyboard": inline}
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)
                return response.status_code == 200
        except Exception as e:
            raise NotificationError("telegram", str(e)) from e


class EmailChannel(NotificationChannel):
    """Email notification channel via SMTP."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_email: str,
        to_email: str | None = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        # Alerts go to the account owner unless a recipient is given.
        self.to_email = to_email or user

    async def send(
        self,
        message: str,
        subject: str | None = None,
        buttons: list[tuple[str, str]] | None = None,  # noqa: ARG002
    ) -> bool:
        """Send email notification."""
        subject = subject or "InternTrack"
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = self.to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "html"))

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            raise NotificationError("email", str(e)) from e


class SmsChannel(NotificationChannel):
    """SMS notification channel via the Twilio Messages API.

    Uses only httpx (no SDK) so it works from the async stack on Vercel
    serverless: one POST to the Twilio REST API with HTTP basic auth and a
    form body ``To`` / ``From`` / ``Body``. ``to_number`` may be ``None``
    (no default recipient) — in that case ``send`` fails closed with
    ``False`` so an owner-level broadcast without a per-user phone never
    raises.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str | None = None,
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.to_number = to_number

    async def send(
        self,
        message: str,
        subject: str | None = None,  # noqa: ARG002 (interface)
        buttons: list[tuple[str, str]] | None = None,  # noqa: ARG002 (interface)
    ) -> bool:
        """Send one SMS via Twilio; fails closed when no recipient is set."""
        if not self.to_number:
            return False
        try:
            import httpx

            url = (
                f"https://api.twilio.com/2010-04-01/Accounts/"
                f"{self.account_sid}/Messages.json"
            )
            # Twilio is an SMS platform — URLs would be long to type; keep
            # the body to a single compact line of plain text.
            body = str(message).strip()
            if len(body) > 160:
                body = body[:157] + "..."
            async with httpx.AsyncClient(
                auth=(self.account_sid, self.auth_token), timeout=15
            ) as client:
                response = await client.post(
                    url,
                    data={
                        "To": self.to_number,
                        "From": self.from_number,
                        "Body": body,
                    },
                )
                return response.status_code in (200, 201)
        except Exception as e:
            raise NotificationError("sms", str(e)) from e


class DiscordChannel(NotificationChannel):
    """Discord webhook notification channel."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(
        self,
        message: str,
        subject: str | None = None,  # noqa: ARG002 (interface)
        buttons: list[tuple[str, str]] | None = None,  # noqa: ARG002
    ) -> bool:
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
            raise NotificationError("discord", str(e)) from e


class SlackChannel(NotificationChannel):
    """Slack webhook notification channel."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(
        self,
        message: str,
        subject: str | None = None,  # noqa: ARG002 (interface)
        buttons: list[tuple[str, str]] | None = None,  # noqa: ARG002
    ) -> bool:
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
            raise NotificationError("slack", str(e)) from e


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

        if (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_phone_number
        ):
            # ``to_number=None`` until a recipient is resolved per user, so
            # an owner-level broadcast without TWILIO_DEFAULT_TO fails closed.
            self._channels["sms"] = SmsChannel(
                settings.twilio_account_sid,
                settings.twilio_auth_token,
                settings.twilio_phone_number,
                settings.twilio_default_to,
            )

    async def notify(
        self,
        channels: list[str],
        message: str,
        subject: str | None = None,
        buttons: list[tuple[str, str]] | None = None,
        recipient: dict | None = None,
    ) -> dict[str, bool]:
        """Send notification to multiple channels.

        ``buttons`` (optional ``(label, url)`` pairs) is passed to channels
        that support inline buttons (Telegram); other channels ignore it.
        ``recipient`` (optional) personalizes delivery per user: ``email``
        overrides the email recipient, ``telegram_chat_id`` overrides the
        Telegram chat and ``phone_number`` targets SMS — every registered
        user gets alerts on *their* devices.
        Records per-channel delivery into the business metrics store.
        ``delivered=False`` covers both a real delivery failure and a channel
        that is not configured (never attempted).
        """
        results = {}
        for channel_name in channels:
            channel = self._channels.get(channel_name)
            if recipient:
                # Per-user delivery: the user's own contact point only. A
                # missing contact fails the channel (delivered=False) instead
                # of leaking to the shared/owner channels.
                channel = self._user_channel(channel_name, recipient)
            if channel:
                try:
                    results[channel_name] = await channel.send(
                        message, subject, buttons
                    )
                except Exception:
                    results[channel_name] = False
                business_metrics_store.record_notification(
                    channel_name,
                    delivered=bool(results[channel_name]),
                )
            else:
                results[channel_name] = False
                business_metrics_store.record_notification(
                    channel_name,
                    delivered=False,
                )
        return results

    def _user_channel(
        self,
        channel_name: str,
        recipient: dict,
    ) -> NotificationChannel | None:
        """A channel instance pointed at a specific user's contact point.

        Email goes to the user's own address (the app's SMTP account stays
        the sender), Telegram goes to the user's own chat id and SMS goes
        to the user's own phone number. When the user has no contact point
        for a channel, ``None`` is returned so delivery fails closed —
        alerts never leak to the shared/owner channels. Discord/Slack
        webhooks are shared and returned as-is.
        """
        if channel_name == "email":
            email = recipient.get("email")
            if email and settings.smtp_user and settings.smtp_password:
                return EmailChannel(
                    settings.smtp_host,
                    settings.smtp_port,
                    settings.smtp_user,
                    settings.smtp_password,
                    settings.email_from,
                    to_email=email,
                )
            return None
        if channel_name == "telegram":
            chat_id = recipient.get("telegram_chat_id")
            if settings.telegram_bot_token and chat_id:
                return TelegramChannel(settings.telegram_bot_token, chat_id)
            return None
        if channel_name == "sms":
            phone = recipient.get("phone_number")
            if (
                settings.twilio_account_sid
                and settings.twilio_auth_token
                and settings.twilio_phone_number
                and phone
            ):
                return SmsChannel(
                    settings.twilio_account_sid,
                    settings.twilio_auth_token,
                    settings.twilio_phone_number,
                    phone,
                )
            return None
        return self._channels.get(channel_name)

    async def notify_all(
        self,
        message: str,
        subject: str | None = None,
        buttons: list[tuple[str, str]] | None = None,
    ) -> dict[str, bool]:
        """Send notification to all configured channels."""
        return await self.notify(
            list(self._channels.keys()),
            message,
            subject,
            buttons,
        )

    def get_configured_channels(self) -> list[str]:
        """Get list of configured channels."""
        return list(self._channels.keys())
