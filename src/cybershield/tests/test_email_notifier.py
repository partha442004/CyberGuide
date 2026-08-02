"""
Tests for the EmailNotifier notification channel.

Covers HTML/text template building, credential validation, send success
and failure paths, SMTP send, and connection testing.
"""

import pytest

from cybershield.notifications.base import (
    NotificationMessage,
    NotificationPriority,
    NotificationType,
)
from cybershield.notifications.email import EmailNotifier


def _message(**overrides) -> NotificationMessage:
    """Build a NotificationMessage with defaults."""
    defaults: dict = {
        "title": "New Job Alert",
        "content": "A new security analyst job was found.",
        "notification_type": NotificationType.INSTANT_ALERT,
        "priority": NotificationPriority.HIGH,
        "url": "https://example.com/job/1",
    }
    defaults.update(overrides)
    return NotificationMessage(**defaults)


def _notifier(**config) -> EmailNotifier:
    cfg = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "sender@example.com",
        "password": "secret",
        "from_email": "sender@example.com",
        "to_emails": ["recruiter@example.com"],
    }
    cfg.update(config)
    return EmailNotifier(cfg)


class TestInit:
    def test_defaults_when_no_config(self):
        notifier = EmailNotifier()
        assert notifier.smtp_host == "smtp.gmail.com"
        assert notifier.smtp_port == 587
        assert notifier.username == ""
        assert notifier.password == ""
        assert notifier.to_emails == []

    def test_config_overrides_defaults(self):
        notifier = _notifier(smtp_host="smtp.outlook.com", smtp_port=465)
        assert notifier.smtp_host == "smtp.outlook.com"
        assert notifier.smtp_port == 465
        assert notifier.username == "sender@example.com"


class TestBuildHtmlTemplate:
    def test_contains_title_and_content(self):
        notifier = _notifier()
        html = notifier._build_html_template(_message())
        assert "New Job Alert" in html
        assert "A new security analyst job was found." in html

    def test_priority_colors(self):
        notifier = _notifier()
        colors = {
            NotificationPriority.LOW: "#6c757d",
            NotificationPriority.MEDIUM: "#0d6efd",
            NotificationPriority.HIGH: "#ffc107",
            NotificationPriority.URGENT: "#dc3545",
        }
        for priority, color in colors.items():
            html = notifier._build_html_template(_message(priority=priority))
            assert color in html

    def test_url_button_included(self):
        notifier = _notifier()
        html = notifier._build_html_template(_message())
        assert "View Details" in html
        assert "https://example.com/job/1" in html

    def test_url_button_omitted_when_no_url(self):
        notifier = _notifier()
        html = notifier._build_html_template(_message(url=None))
        assert "View Details" not in html

    def test_notification_type_title_cased(self):
        notifier = _notifier()
        html = notifier._build_html_template(
            _message(notification_type=NotificationType.DEADLINE_REMINDER)
        )
        assert "Deadline Reminder" in html

    def test_newlines_rendered_as_breaks(self):
        notifier = _notifier()
        html = notifier._build_html_template(_message(content="line1\nline2"))
        assert "<br>" in html


class TestBuildTextVersion:
    def test_structure(self):
        notifier = _notifier()
        text = notifier._build_text_version(_message())
        assert "New Job Alert" in text
        assert "=" * len("New Job Alert") in text
        assert "A new security analyst job was found." in text
        assert "View Details: https://example.com/job/1" in text

    def test_no_url(self):
        notifier = _notifier()
        text = notifier._build_text_version(_message(url=None))
        assert "View Details" not in text


class TestSend:
    @pytest.mark.asyncio
    async def test_send_without_credentials_returns_false(self):
        notifier = EmailNotifier({"username": "", "password": ""})
        assert await notifier.send(_message()) is False

    @pytest.mark.asyncio
    async def test_send_success(self, monkeypatch):
        notifier = _notifier()
        called = {"value": False}

        def fake_send_sync(self, message):
            called["value"] = True

        monkeypatch.setattr(EmailNotifier, "_send_email_sync", fake_send_sync)
        result = await notifier.send(_message())
        assert result is True
        assert called["value"] is True

    @pytest.mark.asyncio
    async def test_send_exception_returns_false(self, monkeypatch):
        notifier = _notifier()

        def fake_send_sync(self, message):
            raise RuntimeError("smtp down")

        monkeypatch.setattr(EmailNotifier, "_send_email_sync", fake_send_sync)
        result = await notifier.send(_message())
        assert result is False


class TestSendEmailSync:
    def test_sends_via_smtp(self, monkeypatch):
        notifier = _notifier()

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                self.sent = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def starttls(self):
                pass

            def login(self, user, password):
                self.sent.append(("login", user, password))

            def sendmail(self, from_addr, to_addrs, msg):
                self.sent.append(("sendmail", from_addr, to_addrs, msg))

        fake_instance = FakeSMTP()
        monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake_instance)

        notifier._send_email_sync(_message())

        assert any(item[0] == "login" for item in fake_instance.sent)
        assert any(item[0] == "sendmail" for item in fake_instance.sent)


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_connection_success(self, monkeypatch):
        notifier = _notifier()

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def starttls(self):
                pass

            def login(self, user, password):
                pass

        monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: FakeSMTP())
        assert await notifier.test_connection() is True

    @pytest.mark.asyncio
    async def test_connection_failure(self, monkeypatch):
        notifier = _notifier()

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def starttls(self):
                pass

            def login(self, user, password):
                raise RuntimeError("auth failed")

        monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: FakeSMTP())
        assert await notifier.test_connection() is False
