"""
Slack Notifier

Sends notifications via Slack webhooks.
"""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import httpx

from cybershield.notifications.base import BaseNotifier, NotificationMessage

logger = logging.getLogger(__name__)


class SlackNotifier(BaseNotifier):
    """
    Slack notification channel.

    Requires:
    - webhook_url: Slack webhook URL
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("slack", config)
        self.webhook_url = config.get("webhook_url", "") if config else ""

    def _build_block_kit(self, message: NotificationMessage) -> list:
        """Build Slack Block Kit message."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": message.title,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message.content[:3000]
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Type:* {message.notification_type.value.replace('_', ' ').title()} | *Priority:* {message.priority.value.upper()}"
                    }
                ]
            }
        ]

        if message.url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Details"
                        },
                        "url": message.url,
                        "style": "primary"
                    }
                ]
            })

        return blocks

    def _build_simple_payload(self, message: NotificationMessage) -> Dict[str, Any]:
        """Build simple Slack payload (fallback)."""
        return {
            "text": f"*{message.title}*\n\n{message.content}",
            "unfurl_links": bool(message.url),
        }

    async def send(self, message: NotificationMessage) -> bool:
        """Send notification via Slack webhook."""
        if not self.webhook_url:
            self.logger.error("Slack webhook URL not configured")
            return False

        # Try Block Kit first, fall back to simple payload
        try:
            payload = {
                "blocks": self._build_block_kit(message),
                "text": message.title,  # Fallback text
            }
        except Exception:
            payload = self._build_simple_payload(message)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            # Slack returns 200 on success
            return response.status_code == 200

    async def test_connection(self) -> bool:
        """Test Slack webhook connection."""
        if not self.webhook_url:
            return False

        try:
            test_message = NotificationMessage(
                title="Test Connection",
                content="CyberShield notification test successful!",
            )
            return await self.send(test_message)
        except Exception as e:
            self.logger.error(f"Slack webhook test failed: {e}")
            return False
