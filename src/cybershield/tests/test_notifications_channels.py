"""
Tests for Discord, Slack, and Telegram notification channels.

Covers embed/block-kit/message building and send/test_connection paths with
a mocked ``httpx.AsyncClient`` (no real network calls).
"""

from typing import Any
from unittest.mock import patch

import pytest

from cybershield.notifications.base import (
    NotificationMessage,
    NotificationPriority,
    NotificationType,
)
from cybershield.notifications.discord import DiscordNotifier
from cybershield.notifications.slack import SlackNotifier
from cybershield.notifications.telegram import TelegramNotifier


def _message(**overrides: Any) -> NotificationMessage:
    """Build a NotificationMessage with sensible defaults."""
    defaults = {
        "title": "Test Alert",
        "content": "This is a test notification",
        "notification_type": NotificationType.INSTANT_ALERT,
        "priority": NotificationPriority.HIGH,
    }
    defaults.update(overrides)
    return NotificationMessage(**defaults)


class FakeResponse:
    """Minimal httpx.Response stand-in."""

    def __init__(self, status_code: int = 200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


class FakeAsyncClient:
    """Context-manager fake for httpx.AsyncClient with a scripted post/get."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *args, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.responses.pop(0)

    async def get(self, url, *args, **kwargs):
        self.get_calls.append(url)
        return self.responses.pop(0)


def _patch_client(module_path: str, responses):
    """Return a context manager patching httpx.AsyncClient in a module."""
    return patch(f"{module_path}.httpx.AsyncClient", return_value=FakeAsyncClient(responses))


# ---------------------------------------------------------------------------
# DiscordNotifier
# ---------------------------------------------------------------------------


class TestDiscordNotifier:
    def test_embed_priority_colors(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})
        for priority, expected in [
            (NotificationPriority.LOW, 0x6C757D),
            (NotificationPriority.MEDIUM, 0x0D6EFD),
            (NotificationPriority.HIGH, 0xFFC107),
            (NotificationPriority.URGENT, 0xDC3545),
        ]:
            embed = notifier._build_embed(_message(priority=priority))
            assert embed["color"] == expected

    def test_embed_includes_url_and_data_fields(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})
        msg = _message(url="https://job.example/1", data={"company": "Acme", "salary": 80000})
        embed = notifier._build_embed(msg)
        assert embed["url"] == "https://job.example/1"
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["Company"] == "Acme"
        assert fields["Salary"] == "80000"

    def test_embed_truncates_content_and_fields(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})
        msg = _message(content="x" * 5000, data={f"key{i}": "v" for i in range(15)})
        embed = notifier._build_embed(msg)
        assert len(embed["description"]) == 4000
        assert len(embed["fields"]) == 10

    @pytest.mark.asyncio
    async def test_send_without_webhook_returns_false(self):
        notifier = DiscordNotifier({})
        assert await notifier.send(_message()) is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})
        with _patch_client("cybershield.notifications.discord", [FakeResponse(204)]):
            result = await notifier.send(_message())
        assert result is True

    @pytest.mark.asyncio
    async def test_send_failure_status(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})
        with _patch_client("cybershield.notifications.discord", [FakeResponse(500)]):
            result = await notifier.send(_message())
        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_without_url(self):
        notifier = DiscordNotifier({})
        assert await notifier.test_connection() is False

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})
        with _patch_client("cybershield.notifications.discord", [FakeResponse(200)]):
            assert await notifier.test_connection() is True

    @pytest.mark.asyncio
    async def test_test_connection_handles_exception(self):
        notifier = DiscordNotifier({"webhook_url": "https://discord.test/hook"})

        class ExplodingClient:
            async def __aenter__(self):
                raise RuntimeError("network down")

            async def __aexit__(self, *exc):
                return False

        with patch(
            "cybershield.notifications.discord.httpx.AsyncClient",
            return_value=ExplodingClient(),
        ):
            assert await notifier.test_connection() is False


# ---------------------------------------------------------------------------
# SlackNotifier
# ---------------------------------------------------------------------------


class TestSlackNotifier:
    def test_build_block_kit(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})
        blocks = notifier._build_block_kit(_message(url="https://job.example/1"))
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == "Test Alert"
        assert blocks[1]["type"] == "section"
        assert blocks[-1]["type"] == "actions"
        assert "View Details" in blocks[-1]["elements"][0]["text"]["text"]

    def test_build_block_kit_without_url(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})
        blocks = notifier._build_block_kit(_message())
        assert blocks[-1]["type"] == "context"
        assert not any(b["type"] == "actions" for b in blocks)

    def test_build_simple_payload(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})
        payload = notifier._build_simple_payload(_message(url="https://job.example/1"))
        assert "Test Alert" in payload["text"]
        assert payload["unfurl_links"] is True

    @pytest.mark.asyncio
    async def test_send_without_webhook_returns_false(self):
        notifier = SlackNotifier({})
        assert await notifier.send(_message()) is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})
        with _patch_client("cybershield.notifications.slack", [FakeResponse(200)]):
            assert await notifier.send(_message()) is True

    @pytest.mark.asyncio
    async def test_send_falls_back_to_simple_payload_on_build_error(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})
        msg = _message()

        # Force _build_block_kit to fail by injecting a broken message attr.
        with patch.object(
            notifier,
            "_build_block_kit",
            side_effect=RuntimeError("build failed"),
        ):
            with _patch_client("cybershield.notifications.slack", [FakeResponse(200)]):
                assert await notifier.send(msg) is True

    @pytest.mark.asyncio
    async def test_test_connection_without_url(self):
        notifier = SlackNotifier({})
        assert await notifier.test_connection() is False

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})
        with _patch_client("cybershield.notifications.slack", [FakeResponse(200)]):
            assert await notifier.test_connection() is True

    @pytest.mark.asyncio
    async def test_test_connection_handles_exception(self):
        notifier = SlackNotifier({"webhook_url": "https://slack.test/hook"})

        with patch.object(
            notifier,
            "send",
            side_effect=RuntimeError("boom"),
        ):
            assert await notifier.test_connection() is False


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------


class TestTelegramNotifier:
    def test_get_api_url(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        assert notifier._get_api_url("sendMessage") == (
            "https://api.telegram.org/bot123:ABC/sendMessage"
        )

    def test_escape_markdown(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        escaped = notifier._escape_markdown("a_b *c* [d](e) f")
        assert "\\_" in escaped
        assert "\\*" in escaped
        assert "\\[" in escaped

    def test_format_message_truncates_long_content(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        formatted = notifier._format_message(_message(content="x" * 5000))
        assert len(formatted) == 4000
        assert formatted.endswith("...")

    def test_format_message_short_content_unchanged(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        msg = _message(content="short")
        assert notifier._format_message(msg) == "short"

    @pytest.mark.asyncio
    async def test_send_without_credentials_returns_false(self):
        notifier = TelegramNotifier({})
        assert await notifier.send(_message()) is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        with _patch_client("cybershield.notifications.telegram", [FakeResponse(200, {"ok": True})]):
            assert await notifier.send(_message()) is True

    @pytest.mark.asyncio
    async def test_send_failure_when_api_returns_not_ok(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        with _patch_client(
            "cybershield.notifications.telegram", [FakeResponse(200, {"ok": False})]
        ):
            assert await notifier.send(_message()) is False

    @pytest.mark.asyncio
    async def test_send_includes_reply_markup_when_url_present(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        with _patch_client(
            "cybershield.notifications.telegram", [FakeResponse(200, {"ok": True})]
        ) as client_factory:
            await notifier.send(_message(url="https://job.example/1"))
            fake_client = client_factory.return_value
            _url, kwargs = fake_client.post_calls[0]
            assert "reply_markup" in kwargs["json"]

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        with _patch_client("cybershield.notifications.telegram", [FakeResponse(200, {"ok": True})]):
            assert await notifier.test_connection() is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        notifier = TelegramNotifier({"bot_token": "123:ABC", "chat_id": "-100"})
        with _patch_client(
            "cybershield.notifications.telegram", [FakeResponse(200, {"ok": False})]
        ):
            assert await notifier.test_connection() is False
