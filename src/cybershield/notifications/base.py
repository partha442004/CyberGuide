"""
Base Notifier

Provides common functionality for all notification channels.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    INSTANT_ALERT = "instant_alert"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_REPORT = "weekly_report"
    MONTHLY_REPORT = "monthly_report"
    DEADLINE_REMINDER = "deadline_reminder"
    SCAM_ALERT = "scam_alert"
    WATCHLIST_MATCH = "watchlist_match"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NotificationMessage:
    """Standardized notification message."""
    title: str
    content: str
    notification_type: NotificationType = NotificationType.INSTANT_ALERT
    priority: NotificationPriority = NotificationPriority.MEDIUM
    data: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "type": self.notification_type.value,
            "priority": self.priority.value,
            "data": self.data,
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseNotifier(ABC):
    """
    Base class for all notification channels.

    Provides:
    - Common configuration
    - Message formatting
    - Error handling
    - Rate limiting
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"cybershield.notifications.{name}")
        self._enabled = config.get("enabled", True) if config else True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """Send a notification. Returns True if successful."""
        pass

    async def send_safe(self, message: NotificationMessage) -> bool:
        """Send notification with error handling."""
        if not self._enabled:
            self.logger.debug(f"Notifier {self.name} is disabled, skipping")
            return False

        try:
            success = await self.send(message)
            if success:
                self.logger.info(f"Notification sent via {self.name}: {message.title}")
            else:
                self.logger.warning(f"Notification failed via {self.name}: {message.title}")
            return success
        except Exception as e:
            self.logger.error(f"Error sending notification via {self.name}: {e}")
            return False

    def _format_job_alert(self, job: Dict[str, Any]) -> str:
        """Format a job alert message."""
        title = job.get("title", "Unknown Position")
        company = job.get("company_name", "Unknown Company")
        location = job.get("location", "Remote")
        url = job.get("url", "")
        scam_score = job.get("scam_score", 0)

        lines = [
            f"🎯 **{title}**",
            f"🏢 {company}",
            f"📍 {location}",
        ]

        if job.get("salary_min"):
            currency = job.get("salary_currency", "USD")
            lines.append(f"💰 {currency} {job['salary_min']:,.0f} - {job.get('salary_max', job['salary_min']):,.0f}")

        if job.get("is_remote"):
            lines.append("🌐 Remote Available")

        if scam_score and scam_score > 30:
            lines.append(f"⚠️ Scam Score: {scam_score}/100")

        if url:
            lines.append(f"\n🔗 [Apply Here]({url})")

        return "\n".join(lines)

    def _format_daily_digest(self, data: Dict[str, Any]) -> str:
        """Format a daily digest message."""
        new_jobs = data.get("new_jobs", 0)
        expiring = data.get("expiring_soon", 0)
        top_skills = data.get("top_skills", [])

        lines = [
            "📊 **Daily CyberGuide Digest**",
            f"\n📈 **{new_jobs}** new opportunities found",
            f"⏰ **{expiring}** jobs expiring soon",
        ]

        if top_skills:
            lines.append(f"\n🔥 Trending Skills: {', '.join(top_skills[:5])}")

        return "\n".join(lines)
