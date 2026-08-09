"""
Tests for the Twilio SMS notification channel.

Covers the SmsChannel itself (Twilio Messages API via httpx), the
NotificationManager per-user wiring (``_user_channel("sms", ...)``), the
``is_twilio_configured`` settings helper, and phone-number capture at
registration.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSmsChannel:
    """SmsChannel send behavior against the Twilio Messages API."""

    @pytest.mark.asyncio
    async def test_no_recipient_fails_closed(self):
        """Without a recipient phone the channel never calls Twilio."""
        from interntrack.services.notification_service import SmsChannel

        channel = SmsChannel("sid123", "tok456", "+15005550006")
        with patch("httpx.AsyncClient") as mock_client:
            result = await channel.send("hello")
        assert result is False
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_success(self):
        from interntrack.services.notification_service import SmsChannel

        channel = SmsChannel("sid123", "tok456", "+15005550006", "+919876543210")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=201))

            result = await channel.send(
                "New SOC Analyst job in Bangalore", subject="Alert"
            )

        assert result is True
        args, kwargs = mock_client.post.call_args
        assert "/Accounts/sid123/Messages.json" in args[0]
        assert kwargs["data"]["To"] == "+919876543210"
        assert kwargs["data"]["From"] == "+15005550006"
        assert kwargs["data"]["Body"] == "New SOC Analyst job in Bangalore"

    @pytest.mark.asyncio
    async def test_long_body_truncated_to_sms_length(self):
        from interntrack.services.notification_service import SmsChannel

        channel = SmsChannel("sid", "tok", "+15005550006", "+919876543210")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=201))

            await channel.send("x" * 300)

        body = mock_client.post.call_args.kwargs["data"]["Body"]
        assert len(body) <= 160
        assert body.endswith("...")

    @pytest.mark.asyncio
    async def test_network_error_raises(self):
        from interntrack.domain.exceptions import NotificationError
        from interntrack.services.notification_service import SmsChannel

        channel = SmsChannel("sid", "tok", "+15005550006", "+919876543210")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("down"))

            with pytest.raises(NotificationError):
                await channel.send("hi")


class TestSmsUserChannel:
    """Per-user SMS delivery via NotificationManager._user_channel."""

    @staticmethod
    def _fake_settings(**overrides):
        base = {
            "telegram_bot_token": None,
            "telegram_chat_id": None,
            "smtp_user": None,
            "smtp_password": None,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "email_from": "x@example.com",
            "discord_webhook_url": None,
            "slack_webhook_url": None,
            "twilio_account_sid": "sid",
            "twilio_auth_token": "tok",  # noqa: S106 (test fixture)
            "twilio_phone_number": "+15005550006",
            "twilio_default_to": None,
            "is_twilio_configured": True,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_sms_with_phone_returns_channel(self):
        from interntrack.services.notification_service import (
            NotificationManager,
            SmsChannel,
        )

        with patch(
            "interntrack.services.notification_service.settings",
            self._fake_settings(),
        ):
            manager = NotificationManager.__new__(NotificationManager)
            channel = manager._user_channel("sms", {"phone_number": "+919876543210"})
        assert isinstance(channel, SmsChannel)
        assert channel.to_number == "+919876543210"
        assert channel.from_number == "+15005550006"

    def test_sms_without_phone_returns_none(self):
        from interntrack.services.notification_service import NotificationManager

        with patch(
            "interntrack.services.notification_service.settings",
            self._fake_settings(),
        ):
            manager = NotificationManager.__new__(NotificationManager)
            assert manager._user_channel("sms", {"email": "a@b.com"}) is None

    def test_sms_fails_closed_when_twilio_not_configured(self):
        from interntrack.services.notification_service import NotificationManager

        with patch(
            "interntrack.services.notification_service.settings",
            self._fake_settings(twilio_account_sid=None),
        ):
            manager = NotificationManager.__new__(NotificationManager)
            assert (
                manager._user_channel("sms", {"phone_number": "+919876543210"}) is None
            )


class TestTwilioConfig:
    """Settings helper for SMS configuration."""

    def test_is_twilio_configured(self):
        from interntrack.config import Settings

        configured = Settings(
            twilio_account_sid="sid",
            twilio_auth_token="tok",  # noqa: S106 (test fixture)
            twilio_phone_number="+15005550006",
            _env_file=None,
        )
        assert configured.is_twilio_configured

        partial = Settings(
            twilio_account_sid="sid",
            twilio_auth_token="tok",  # noqa: S106 (test fixture)
            _env_file=None,
        )
        assert not partial.is_twilio_configured

        empty = Settings(_env_file=None)
        assert not empty.is_twilio_configured


class TestRegisterWithPhone:
    """Phone number is captured + normalized at registration."""

    @pytest.mark.asyncio
    async def test_register_stores_normalized_phone(self, client):
        resp = await client.post(
            "/api/v1/users/register",
            json={
                "name": "SMS Tester",
                "email": "sms-tester@example.com",
                "phone_number": "+91 98765 43210",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["phone_number"] == "+919876543210"

        # The stored profile carries the normalized phone too.
        listing = await client.get("/api/v1/users")
        profiles = listing.json().get("users") or []
        mine = next(p for p in profiles if p["email"] == "sms-tester@example.com")
        assert mine["phone_number"] == "+919876543210"

    @pytest.mark.asyncio
    async def test_register_bare_10_digit_gets_india_default(self, client):
        """A bare 10-digit number is assumed to be an Indian mobile (+91)."""
        resp = await client.post(
            "/api/v1/users/register",
            json={
                "name": "Bare Phone",
                "email": "bare-phone@example.com",
                "phone_number": "98765 43210",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["phone_number"] == "+919876543210"

    @pytest.mark.asyncio
    async def test_register_invalid_phone_becomes_none(self, client):
        resp = await client.post(
            "/api/v1/users/register",
            json={
                "name": "Bad Phone",
                "email": "bad-phone@example.com",
                "phone_number": "++",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json().get("phone_number") is None

    @pytest.mark.asyncio
    async def test_register_without_phone_ok(self, client):
        resp = await client.post(
            "/api/v1/users/register",
            json={"name": "No Phone", "email": "no-phone@example.com"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json().get("phone_number") is None


class TestSmsDigestRouting:
    """The daily digest routes SMS through the plain-text path."""

    @pytest.mark.asyncio
    async def test_deliver_alert_sends_plain_text_to_sms(self):
        from interntrack.scheduler.jobs import _deliver_alert

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["sms"]
        manager.notify = AsyncMock(return_value={"sms": True})
        user = SimpleNamespace(
            id="u1",
            email="u@example.com",
            telegram_chat_id=None,
            phone_number="+919876543210",
            location="Chennai",
        )

        with (
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="<div>html email body</div>"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_daily_report_message",
                new=AsyncMock(
                    return_value="🔐 3 new security jobs — apply now\nhttps://x"
                ),
            ),
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(return_value={}),
            ),
        ):
            results = await _deliver_alert(
                manager,
                ["sms"],
                {"summary": {}, "new_jobs": []},
                AsyncMock(),
                user=user,
            )

        assert results == {"sms": True}
        manager.notify.assert_awaited_once()
        args, kwargs = manager.notify.await_args
        assert args[0] == ["sms"]
        # SMS gets the plain-text message — never the HTML email body.
        assert "<div>" not in args[1]
        assert "https://x" in args[1]
        assert kwargs["recipient"]["phone_number"] == "+919876543210"
