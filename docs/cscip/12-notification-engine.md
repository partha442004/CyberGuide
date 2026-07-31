# CyberShield Career Intelligence Platform (CSCIP) - Notification Engine

## Overview

The Notification Engine delivers alerts across 5 channels (Telegram, Email, Discord, Slack, Push) with support for instant alerts, daily/weekly/monthly reports, and watchlist matches.

---

## Notification Channels

| Channel | Technology | Free Tier | Best For |
|---------|------------|-----------|----------|
| Telegram | python-telegram-bot | Unlimited | Instant alerts |
| Email | Gmail SMTP | 500/day | Reports, detailed info |
| Discord | Webhook | Unlimited | Community alerts |
| Slack | Webhook | Limited | Team notifications |
| Push | Web Push API | Unlimited | Mobile alerts |

---

## Notification Types

### 1. Instant Alerts
- New job matching watchlist keyword/company
- Scam detected for saved job
- Application status change
- Deadline approaching (24h, 48h)

### 2. Daily Report (6 AM)
```
📊 Daily Report - {date}

🔍 New Opportunities
• {count} new internships found
• {count} new jobs found
• {count} remote jobs available

💰 Top Opportunities
• Highest salary: {job} - {salary}
• Highest stipend: {job} - {stipend}

⏰ Closing Today
• {job} at {company} ({openings} positions)

⏰ Closing Tomorrow
• {job} at {company}

🎯 Must Apply (High Match)
• {count} jobs matching your skills > 80%

🏢 Top Companies Hiring
• {company} ({count} openings)

🔧 Top Skills in Demand
• {skill} ({growth}% growth)
```

### 3. Weekly Report (Monday 8 AM)
- Top hiring companies
- Hiring/salary/skill trends
- Upcoming hiring predictions
- New certifications/CTFs

### 4. Monthly Report (1st of month)
- Complete analytics
- Market insights
- Career recommendations

---

## Implementation Code

```python
# src/cybershield/notifications/manager.py

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.config import get_settings
from cybershield.domain.enums import NotificationChannel
from cybershield.notifications.base import NotificationChannel as BaseChannel
from cybershield.notifications.telegram import TelegramChannel
from cybershield.notifications.email import EmailChannel
from cybershield.notifications.discord import DiscordChannel
from cybershield.notifications.slack import SlackChannel
from cybershield.notifications.push import PushChannel
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class NotificationManager:
    """Manager for multi-channel notifications."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._channels: Dict[str, BaseChannel] = {}
        self._setup_channels()
    
    def _setup_channels(self):
        """Setup configured notification channels."""
        if settings.is_telegram_configured:
            self._channels["telegram"] = TelegramChannel(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
            )
        
        if settings.is_email_configured:
            self._channels["email"] = EmailChannel(
                host=settings.smtp_host,
                port=settings.smtp_port,
                user=settings.smtp_user,
                password=settings.smtp_password,
                from_email=settings.email_from,
            )
        
        if settings.is_discord_configured:
            self._channels["discord"] = DiscordChannel(
                webhook_url=settings.discord_webhook_url,
            )
        
        if settings.is_slack_configured:
            self._channels["slack"] = SlackChannel(
                webhook_url=settings.slack_webhook_url,
            )
        
        # Push notifications (always available)
        self._channels["push"] = PushChannel()
    
    async def notify(
        self,
        channels: List[str],
        message: str,
        subject: Optional[str] = None,
        priority: str = "normal",
    ) -> Dict[str, bool]:
        """Send notification to multiple channels."""
        results = {}
        
        for channel_name in channels:
            channel = self._channels.get(channel_name)
            if channel:
                try:
                    results[channel_name] = await channel.send(
                        message=message,
                        subject=subject,
                        priority=priority,
                    )
                except Exception as e:
                    logger.error(f"Failed to send via {channel_name}: {e}")
                    results[channel_name] = False
            else:
                results[channel_name] = False
        
        return results
    
    async def notify_all(
        self,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Send notification to all configured channels."""
        return await self.notify(
            channels=list(self._channels.keys()),
            message=message,
            subject=subject,
        )
    
    async def send_instant_alert(
        self,
        job_data: dict,
        match_type: str,
        match_score: float,
    ):
        """Send instant alert for job match."""
        message = self._format_instant_alert(job_data, match_type, match_score)
        
        await self.notify(
            channels=["telegram", "push"],
            message=message,
            subject=f"New {match_type} match: {job_data.get('title')}",
            priority="high",
        )
    
    async def send_scam_alert(self, job_data: dict, scam_score: int):
        """Send scam alert."""
        message = f"""🚨 SCAM ALERT

⚠️ Suspicious job detected and blocked:

Title: {job_data.get('title')}
Company: {job_data.get('company')}
Scam Score: {scam_score}/100

This job has been flagged as potentially fraudulent and will not appear in your listings."""
        
        await self.notify(
            channels=["telegram", "email"],
            message=message,
            subject="⚠️ Scam Alert - Suspicious Job Detected",
            priority="urgent",
        )
    
    async def send_deadline_reminder(self, job_data: dict, hours_left: int):
        """Send deadline reminder."""
        message = f"""⏰ Deadline Reminder

Job: {job_data.get('title')}
Company: {job_data.get('company')}
Deadline: {hours_left} hours remaining

Apply now: {job_data.get('url')}"""
        
        await self.notify(
            channels=["telegram", "push"],
            message=message,
            subject=f"⏰ Deadline in {hours_left}h: {job_data.get('title')}",
        )
    
    async def send_daily_report(self, report_data: dict):
        """Send daily report."""
        message = self._format_daily_report(report_data)
        
        await self.notify(
            channels=["telegram", "email"],
            message=message,
            subject=f"📊 Daily Report - {report_data.get('date')}",
        )
    
    async def send_weekly_report(self, report_data: dict):
        """Send weekly report."""
        message = self._format_weekly_report(report_data)
        
        await self.notify(
            channels=["email"],
            message=message,
            subject=f"📈 Weekly Report - {report_data.get('week')}",
        )
    
    def _format_instant_alert(self, job_data: dict, match_type: str, score: float) -> str:
        """Format instant alert message."""
        return f"""🎯 New Match Found!

Type: {match_type.title()}
Match Score: {score:.1f}%

Job: {job_data.get('title')}
Company: {job_data.get('company')}
Location: {job_data.get('location', 'Remote')}
Salary: {job_data.get('salary_min', 'N/A')} - {job_data.get('salary_max', 'N/A')}

Apply: {job_data.get('url')}"""
    
    def _format_daily_report(self, data: dict) -> str:
        """Format daily report."""
        summary = data.get("summary", {})
        return f"""📊 Daily Report - {data.get('date')}

🔍 New Opportunities
• {summary.get('new_internships', 0)} new internships
• {summary.get('new_jobs', 0)} new jobs
• {summary.get('remote_jobs', 0)} remote jobs

💰 Top Opportunities
{self._format_list(data.get('top_opportunities', []))}

⏰ Closing Today
{self._format_list(data.get('closing_today', []))}

🎯 Must Apply
{data.get('must_apply_count', 0)} jobs matching your skills > 80%"""
    
    def _format_weekly_report(self, data: dict) -> str:
        """Format weekly report."""
        return f"""📈 Weekly Report - {data.get('week')}

🏢 Top Hiring Companies
{self._format_list(data.get('top_companies', []))}

📊 Trends
• Hiring: {data.get('hiring_trend', 'N/A')}
• Salary: {data.get('salary_trend', 'N/A')}
• Skills: {data.get('skill_trend', 'N/A')}

🔮 Upcoming
{self._format_list(data.get('upcoming_hiring', []))}"""
    
    def _format_list(self, items: list) -> str:
        """Format list items for notification."""
        if not items:
            return "• No items"
        return "\n".join(f"• {item}" for item in items[:5])
    
    def get_configured_channels(self) -> List[str]:
        """Get list of configured channels."""
        return list(self._channels.keys())
```

---

## Telegram Channel

```python
# src/cybershield/notifications/telegram.py

import httpx
from cybershield.notifications.base import NotificationChannel
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramChannel(NotificationChannel):
    """Telegram notification channel."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send(self, message: str, subject: str = None, priority: str = "normal") -> bool:
        """Send Telegram message."""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)
                return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `notifications_sent_total` | Total notifications sent |
| `notifications_by_channel` | Count per channel |
| `notifications_success_rate` | Success rate |
| `notifications_delivery_time_ms` | Average delivery time |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 13: Dashboard](./13-dashboard.md)
