"""
Discord Notifier

Sends notifications via Discord webhooks.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from cybershield.notifications.base import BaseNotifier, NotificationMessage

logger = logging.getLogger(__name__)


class DiscordNotifier(BaseNotifier):
    """
    Discord notification channel.

    Requires:
    - webhook_url: Discord webhook URL
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("discord", config)
        self.webhook_url = config.get("webhook_url", "") if config else ""

    def _build_embed(self, message: NotificationMessage) -> Dict[str, Any]:
        """Build Discord embed from notification message."""
        priority_colors = {
            "low": 0x6C757D,  # Gray
            "medium": 0x0D6EFD,  # Blue
            "high": 0xFFC107,  # Yellow
            "urgent": 0xDC3545,  # Red
        }
        color = priority_colors.get(message.priority.value, 0x0D6EFD)

        embed = {
            "title": message.title,
            "description": message.content[:4000],  # Discord limit
            "color": color,
            "timestamp": message.timestamp.isoformat(),
            "footer": {"text": "CyberGuide Career Intelligence Platform"},
        }

        if message.url:
            embed["url"] = message.url

        if message.data:
            fields = []
            for key, value in list(message.data.items())[:10]:  # Max 10 fields
                fields.append(
                    {
                        "name": key.replace("_", " ").title(),
                        "value": str(value)[:100],
                        "inline": True,
                    }
                )
            if fields:
                embed["fields"] = fields

        return embed

    async def send(self, message: NotificationMessage) -> bool:
        """Send notification via Discord webhook."""
        if not self.webhook_url:
            self.logger.error("Discord webhook URL not configured")
            return False

        payload = {
            "username": "CyberGuide",
            "avatar_url": "https://example.com/cybershield-avatar.png",
            "embeds": [self._build_embed(message)],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
            )

            # Discord returns 204 No Content on success
            return response.status_code in (200, 204)

    async def test_connection(self) -> bool:
        """Test Discord webhook connection."""
        if not self.webhook_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.webhook_url)
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Discord webhook test failed: {e}")
            return False
