"""
Telegram Notifier

Sends notifications via Telegram Bot API.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from cybershield.notifications.base import BaseNotifier, NotificationMessage

logger = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """
    Telegram notification channel.

    Requires:
    - bot_token: Telegram bot token from @BotFather
    - chat_id: Target chat/channel ID
    """

    API_BASE = "https://api.telegram.org"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("telegram", config)
        self.bot_token = config.get("bot_token", "") if config else ""
        self.chat_id = config.get("chat_id", "") if config else ""
        self.parse_mode = config.get("parse_mode", "Markdown") if config else "Markdown"

    def _get_api_url(self, method: str) -> str:
        """Build Telegram API URL."""
        return f"{self.API_BASE}/bot{self.bot_token}/{method}"

    def _escape_markdown(self, text: str) -> str:
        """Escape markdown characters for Telegram."""
        special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    def _format_message(self, message: NotificationMessage) -> str:
        """Format message for Telegram."""
        # Telegram has a 4096 character limit
        content = message.content
        if len(content) > 4000:
            content = content[:3997] + "..."
        return content

    async def send(self, message: NotificationMessage) -> bool:
        """Send notification via Telegram."""
        if not self.bot_token or not self.chat_id:
            self.logger.error("Telegram bot_token or chat_id not configured")
            return False

        formatted_message = self._format_message(message)

        payload = {
            "chat_id": self.chat_id,
            "text": formatted_message,
            "parse_mode": self.parse_mode,
            "disable_web_page_preview": not bool(message.url),
        }

        if message.url:
            import json
            payload["reply_markup"] = json.dumps({
                "inline_keyboard": [[{"text": "View Details", "url": message.url}]]
            })

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._get_api_url("sendMessage"),
                json=payload,
            )
            result = response.json()
            return result.get("ok", False)

    async def test_connection(self) -> bool:
        """Test Telegram bot connection."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self._get_api_url("getMe"))
            result = response.json()
            return result.get("ok", False)
