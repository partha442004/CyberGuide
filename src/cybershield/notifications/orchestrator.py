"""
Notification Orchestrator

Manages and coordinates all notification channels.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

from cybershield.notifications.base import (
    BaseNotifier,
    NotificationMessage,
    NotificationType,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


class NotificationOrchestrator:
    """
    Orchestrates notifications across multiple channels.

    Features:
    - Register/unregister notification channels
    - Send to single or multiple channels
    - Priority-based routing
    - Retry logic
    - Statistics tracking
    """

    def __init__(self):
        self._channels: Dict[str, BaseNotifier] = {}
        self._stats: Dict[str, Dict[str, int]] = {}

    def register(self, name: str, notifier: BaseNotifier) -> None:
        """Register a notification channel."""
        self._channels[name] = notifier
        self._stats[name] = {"sent": 0, "failed": 0}
        logger.info(f"Registered notification channel: {name}")

    def unregister(self, name: str) -> None:
        """Unregister a notification channel."""
        self._channels.pop(name, None)
        self._stats.pop(name, None)

    def get_channel(self, name: str) -> Optional[BaseNotifier]:
        """Get a notification channel by name."""
        return self._channels.get(name)

    def list_channels(self) -> List[str]:
        """List all registered channels."""
        return list(self._channels.keys())

    def get_enabled_channels(self) -> List[str]:
        """List all enabled channels."""
        return [
            name for name, channel in self._channels.items()
            if channel.enabled
        ]

    async def send_to_channel(
        self,
        channel_name: str,
        message: NotificationMessage,
    ) -> bool:
        """Send notification to a specific channel."""
        channel = self._channels.get(channel_name)
        if not channel:
            logger.warning(f"Channel {channel_name} not found")
            return False

        success = await channel.send_safe(message)

        # Update stats
        if channel_name in self._stats:
            if success:
                self._stats[channel_name]["sent"] += 1
            else:
                self._stats[channel_name]["failed"] += 1

        return success

    async def send_to_channels(
        self,
        channel_names: List[str],
        message: NotificationMessage,
    ) -> Dict[str, bool]:
        """Send notification to multiple channels."""
        results = {}

        tasks = [
            self.send_to_channel(name, message)
            for name in channel_names
        ]

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for name, outcome in zip(channel_names, outcomes):
            if isinstance(outcome, Exception):
                logger.error(f"Error sending to {name}: {outcome}")
                results[name] = False
            else:
                results[name] = outcome

        return results

    async def send_to_all(
        self,
        message: NotificationMessage,
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Send notification to all enabled channels."""
        exclude = exclude or []
        channels = [
            name for name in self.get_enabled_channels()
            if name not in exclude
        ]
        return await self.send_to_channels(channels, message)

    async def send_job_alert(
        self,
        job: Dict[str, Any],
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Send a job alert notification."""
        # Format job content
        content = self._format_job_content(job)

        message = NotificationMessage(
            title=f"🎯 New Job: {job.get('title', 'Unknown')}",
            content=content,
            notification_type=NotificationType.WATCHLIST_MATCH,
            priority=NotificationPriority.HIGH,
            url=job.get("url"),
            data={
                "company": job.get("company_name"),
                "location": job.get("location"),
                "source": job.get("source"),
            }
        )

        if channels:
            return await self.send_to_channels(channels, message)
        return await self.send_to_all(message)

    async def send_scam_alert(
        self,
        job: Dict[str, Any],
        scam_score: float,
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Send a scam alert notification."""
        content = (
            f"⚠️ **Potential Scam Detected**\n\n"
            f"**Job:** {job.get('title', 'Unknown')}\n"
            f"**Company:** {job.get('company_name', 'Unknown')}\n"
            f"**Scam Score:** {scam_score}/100\n\n"
            f"This job has been flagged for suspicious activity. "
            f"Please verify carefully before applying."
        )

        message = NotificationMessage(
            title="⚠️ Scam Alert",
            content=content,
            notification_type=NotificationType.SCAM_ALERT,
            priority=NotificationPriority.URGENT,
            url=job.get("url"),
        )

        if channels:
            return await self.send_to_channels(channels, message)
        return await self.send_to_all(message, exclude=["telegram"])  # Don't spam Telegram with scam alerts

    async def send_daily_digest(
        self,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Send daily digest notification."""
        content = self._format_daily_digest(data)

        message = NotificationMessage(
            title="📊 Daily CyberShield Digest",
            content=content,
            notification_type=NotificationType.DAILY_DIGEST,
            priority=NotificationPriority.LOW,
        )

        if channels:
            return await self.send_to_channels(channels, message)
        return await self.send_to_all(message)

    def _format_job_content(self, job: Dict[str, Any]) -> str:
        """Format job content for notification."""
        lines = [
            f"**{job.get('title', 'Unknown Position')}**",
            f"🏢 {job.get('company_name', 'Unknown Company')}",
            f"📍 {job.get('location', 'Remote')}",
        ]

        if job.get("salary_min"):
            currency = job.get("salary_currency", "USD")
            lines.append(f"💰 {currency} {job['salary_min']:,.0f} - {job.get('salary_max', job['salary_min']):,.0f}")

        if job.get("is_remote"):
            lines.append("🌐 Remote Available")

        if job.get("required_skills"):
            skills = job["required_skills"][:5]
            lines.append(f"🛠️ Skills: {', '.join(skills)}")

        return "\n".join(lines)

    def _format_daily_digest(self, data: Dict[str, Any]) -> str:
        """Format daily digest content."""
        lines = [
            f"📈 **{data.get('new_jobs', 0)}** new opportunities found",
            f"⏰ **{data.get('expiring_soon', 0)}** jobs expiring soon",
            f"🔥 **{data.get('high_match', 0)}** high-match jobs",
        ]

        if data.get("top_skills"):
            lines.append(f"\n🎯 Trending: {', '.join(data['top_skills'][:5])}")

        if data.get("top_companies"):
            lines.append(f"🏢 Top Hiring: {', '.join(data['top_companies'][:3])}")

        return "\n".join(lines)

    async def send_report(
        self,
        report_type: str,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Send a report notification (daily/weekly/monthly)."""
        title = data.get("title", f"📊 {report_type.title()} Report")
        content = self._format_report(data)

        type_map = {
            "daily": NotificationType.DAILY_DIGEST,
            "weekly": NotificationType.WEEKLY_REPORT,
            "monthly": NotificationType.MONTHLY_REPORT,
        }
        priority_map = {
            "daily": NotificationPriority.LOW,
            "weekly": NotificationPriority.LOW,
            "monthly": NotificationPriority.NORMAL,
        }

        message = NotificationMessage(
            title=title,
            content=content,
            notification_type=type_map.get(report_type, NotificationType.DAILY_DIGEST),
            priority=priority_map.get(report_type, NotificationPriority.LOW),
        )

        if channels:
            return await self.send_to_channels(channels, message)
        return await self.send_to_all(message)

    def _format_report(self, data: Dict[str, Any]) -> str:
        """Format report content for notification."""
        lines = []

        if data.get("period"):
            lines.append(f"📅 **Period:** {data['period']}")

        if data.get("new_jobs") is not None:
            lines.append(f"📈 **{data.get('new_jobs', 0)}** new opportunities")

        if data.get("total_jobs") is not None:
            lines.append(f"💼 **{data.get('total_jobs', 0)}** total jobs tracked")

        if data.get("applications_submitted") is not None:
            lines.append(f"📝 **{data.get('applications_submitted', 0)}** applications submitted")

        if data.get("success_rate") is not None:
            lines.append(f"✅ **{data.get('success_rate', 0)}%** success rate")

        if data.get("expiring_soon") is not None:
            lines.append(f"⏰ **{data.get('expiring_soon', 0)}** jobs expiring soon")

        if data.get("expiring_next_week") is not None:
            lines.append(f"⏰ **{data.get('expiring_next_week', 0)}** jobs expiring next week")

        if data.get("avg_salary_range"):
            lines.append(f"💰 Avg Salary: {data['avg_salary_range']}")

        if data.get("remote_percentage") is not None:
            lines.append(f"🌐 **{data['remote_percentage']}%** remote jobs")

        if data.get("top_companies"):
            companies = data["top_companies"][:5]
            if isinstance(companies[0], tuple):
                companies = [f"{c[0]} ({c[1]})" for c in companies]
            lines.append(f"\n🏢 Top Companies: {', '.join(companies)}")

        if data.get("top_skills"):
            skills = data["top_skills"][:5]
            lines.append(f"\n🎯 Trending Skills: {', '.join(skills)}")

        if data.get("job_types"):
            types = data["job_types"][:5]
            if isinstance(types[0], tuple):
                types = [f"{t[0]} ({t[1]})" for t in types]
            lines.append(f"\n📊 Job Types: {', '.join(types)}")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        return {
            "channels": self.list_channels(),
            "enabled": self.get_enabled_channels(),
            "stats": self._stats.copy(),
        }


def create_default_orchestrator(config: Dict[str, Any]) -> NotificationOrchestrator:
    """Create a notification orchestrator with default channels."""
    from cybershield.notifications.telegram import TelegramNotifier
    from cybershield.notifications.email import EmailNotifier
    from cybershield.notifications.discord import DiscordNotifier
    from cybershield.notifications.slack import SlackNotifier

    orchestrator = NotificationOrchestrator()

    # Register channels based on config
    if config.get("telegram"):
        orchestrator.register("telegram", TelegramNotifier(config["telegram"]))

    if config.get("email"):
        orchestrator.register("email", EmailNotifier(config["email"]))

    if config.get("discord"):
        orchestrator.register("discord", DiscordNotifier(config["discord"]))

    if config.get("slack"):
        orchestrator.register("slack", SlackNotifier(config["slack"]))

    return orchestrator
