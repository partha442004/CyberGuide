"""
Tests for Notifications

Tests for notification channels and orchestrator.
"""

from cybershield.notifications.base import (
    NotificationMessage,
    NotificationPriority,
    NotificationType,
)
from cybershield.notifications.email import EmailNotifier
from cybershield.notifications.orchestrator import NotificationOrchestrator


class TestNotificationMessage:
    """Tests for NotificationMessage."""

    def test_create_message(self):
        """Test creating a notification message."""
        msg = NotificationMessage(
            title="Test Alert",
            content="This is a test",
            notification_type=NotificationType.INSTANT_ALERT,
            priority=NotificationPriority.HIGH,
        )
        assert msg.title == "Test Alert"
        assert msg.priority == NotificationPriority.HIGH

    def test_to_dict(self):
        """Test dictionary conversion."""
        msg = NotificationMessage(title="Test", content="Content")
        data = msg.to_dict()
        assert data["title"] == "Test"
        assert "timestamp" in data


class TestEmailNotifier:
    """Tests for EmailNotifier."""

    def test_build_html_template(self):
        """Test HTML email template generation."""
        notifier = EmailNotifier({"smtp_host": "smtp.test.com"})
        msg = NotificationMessage(title="Test", content="Hello World")
        html = notifier._build_html_template(msg)
        assert "<html>" in html
        assert "Test" in html

    def test_build_text_version(self):
        """Test plain text email generation."""
        notifier = EmailNotifier({"smtp_host": "smtp.test.com"})
        msg = NotificationMessage(title="Test", content="Hello World")
        text = notifier._build_text_version(msg)
        assert "Test" in text
        assert "CyberGuide" in text


class TestNotificationOrchestrator:
    """Tests for NotificationOrchestrator."""

    def test_register_channel(self):
        """Test registering a notification channel."""
        orch = NotificationOrchestrator()
        email = EmailNotifier({"smtp_host": "smtp.test.com"})
        orch.register("email", email)
        assert "email" in orch.list_channels()

    def test_list_channels(self):
        """Test listing channels."""
        orch = NotificationOrchestrator()
        assert isinstance(orch.list_channels(), list)

    def test_get_enabled_channels(self):
        """Test getting enabled channels."""
        orch = NotificationOrchestrator()
        email = EmailNotifier({"smtp_host": "smtp.test.com"})
        orch.register("email", email)
        enabled = orch.get_enabled_channels()
        assert "email" in enabled

    def test_get_stats(self):
        """Test getting statistics."""
        orch = NotificationOrchestrator()
        stats = orch.get_stats()
        assert "channels" in stats
        assert "stats" in stats

    def test_format_job_content(self):
        """Test job content formatting."""
        orch = NotificationOrchestrator()
        job = {
            "title": "Security Analyst",
            "company_name": "Tech Corp",
            "location": "Remote",
            "required_skills": ["Python", "SIEM"],
        }
        content = orch._format_job_content(job)
        assert "Security Analyst" in content
        assert "Tech Corp" in content
