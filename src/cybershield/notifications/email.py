"""
Email Notifier

Sends notifications via SMTP (Gmail, Outlook, etc.).
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import asyncio
from cybershield.notifications.base import BaseNotifier, NotificationMessage

logger = logging.getLogger(__name__)


class EmailNotifier(BaseNotifier):
    """
    Email notification channel.

    Requires:
    - smtp_host: SMTP server host
    - smtp_port: SMTP server port
    - username: Email username
    - password: Email password/app password
    - from_email: Sender email address
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("email", config)
        self.smtp_host = config.get("smtp_host", "smtp.gmail.com") if config else "smtp.gmail.com"
        self.smtp_port = config.get("smtp_port", 587) if config else 587
        self.username = config.get("username", "") if config else ""
        self.password = config.get("password", "") if config else ""
        self.from_email = config.get("from_email", "") if config else ""
        self.to_emails = config.get("to_emails", []) if config else []

    def _build_html_template(self, message: NotificationMessage) -> str:
        """Build HTML email template."""
        priority_colors = {
            "low": "#6c757d",
            "medium": "#0d6efd",
            "high": "#ffc107",
            "urgent": "#dc3545",
        }
        color = priority_colors.get(message.priority.value, "#0d6efd")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa;">
    <div style="background-color: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div style="border-left: 4px solid {color}; padding-left: 15px; margin-bottom: 20px;">
            <h1 style="margin: 0; color: #333; font-size: 24px;">{message.title}</h1>
            <p style="margin: 5px 0 0; color: #666; font-size: 14px;">
                {message.notification_type.value.replace('_', ' ').title()} • 
                {message.timestamp.strftime('%B %d, %Y at %I:%M %p UTC')}
            </p>
        </div>
        
        <div style="color: #444; line-height: 1.6; font-size: 16px;">
            {message.content.replace(chr(10), '<br>')}
        </div>
        
        {f'<div style="margin-top: 20px;"><a href="{message.url}" style="display: inline-block; background-color: {color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">View Details</a></div>' if message.url else ''}
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #999; font-size: 12px;">
            <p>CyberGuide Career Intelligence Platform</p>
            <p>To unsubscribe, update your notification preferences.</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _build_text_version(self, message: NotificationMessage) -> str:
        """Build plain text version."""
        lines = [
            message.title,
            "=" * len(message.title),
            "",
            message.content,
            "",
        ]
        if message.url:
            lines.append(f"View Details: {message.url}")
        lines.extend([
            "",
            "---",
            "CyberGuide Career Intelligence Platform",
        ])
        return "\n".join(lines)

    async def send(self, message: NotificationMessage) -> bool:
        """Send notification via email."""
        if not self.username or not self.password:
            self.logger.error("Email credentials not configured")
            return False

        try:
            await asyncio.to_thread(self._send_email_sync, message)
            return True
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False

    def _send_email_sync(self, message: NotificationMessage) -> None:
        """Synchronous email sending (runs in thread)."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.title
        msg["From"] = self.from_email or self.username
        msg["To"] = ", ".join(self.to_emails)

        # Add plain text version
        text_content = self._build_text_version(message)
        msg.attach(MIMEText(text_content, "plain"))

        # Add HTML version
        html_content = self._build_html_template(message)
        msg.attach(MIMEText(html_content, "html"))

        # Send email
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(
                self.from_email or self.username,
                self.to_emails,
                msg.as_string(),
            )

    async def test_connection(self) -> bool:
        """Test SMTP connection."""
        try:
            import smtplib
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
            return True
        except Exception as e:
            self.logger.error(f"SMTP connection test failed: {e}")
            return False
