"""
Tests for the BaseNotifier common functionality.

Covers enable/disable, send_safe success/failure/disabled/exception paths,
and the job-alert / daily-digest formatters.
"""

import pytest

from cybershield.notifications.base import (
    BaseNotifier,
    NotificationMessage,
    NotificationPriority,
    NotificationType,
)


class _ConcreteNotifier(BaseNotifier):
    """Concrete notifier for testing BaseNotifier behavior."""

    def __init__(self, config=None, send_result: bool = True):
        super().__init__("test", config)
        self._send_result = send_result
        self.send_called = False

    async def send(self, message: NotificationMessage) -> bool:
        self.send_called = True
        return self._send_result


def _message(**overrides) -> NotificationMessage:
    """Build a NotificationMessage with defaults."""
    defaults: dict = {
        "title": "Test",
        "content": "Content",
        "notification_type": NotificationType.INSTANT_ALERT,
        "priority": NotificationPriority.MEDIUM,
    }
    defaults.update(overrides)
    return NotificationMessage(**defaults)


class TestEnableDisable:
    def test_enabled_by_default(self):
        notifier = _ConcreteNotifier()
        assert notifier.enabled is True

    def test_disabled_when_config_says_so(self):
        notifier = _ConcreteNotifier(config={"enabled": False})
        assert notifier.enabled is False

    def test_disable_and_enable(self):
        notifier = _ConcreteNotifier()
        notifier.disable()
        assert notifier.enabled is False
        notifier.enable()
        assert notifier.enabled is True


class TestSendSafe:
    @pytest.mark.asyncio
    async def test_disabled_returns_false_without_sending(self):
        notifier = _ConcreteNotifier(config={"enabled": False})
        result = await notifier.send_safe(_message())
        assert result is False
        assert notifier.send_called is False

    @pytest.mark.asyncio
    async def test_success_returns_true(self):
        notifier = _ConcreteNotifier(send_result=True)
        assert await notifier.send_safe(_message()) is True
        assert notifier.send_called is True

    @pytest.mark.asyncio
    async def test_failure_returns_false(self):
        notifier = _ConcreteNotifier(send_result=False)
        assert await notifier.send_safe(_message()) is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        class ThrowingNotifier(_ConcreteNotifier):
            async def send(self, message: NotificationMessage) -> bool:
                raise RuntimeError("boom")

        notifier = ThrowingNotifier()
        assert await notifier.send_safe(_message()) is False


class TestFormatJobAlert:
    def test_full_job(self):
        notifier = _ConcreteNotifier()
        text = notifier._format_job_alert(
            {
                "title": "Security Engineer",
                "company_name": "Acme",
                "location": "Remote",
                "url": "https://job.example/1",
                "salary_min": 100000,
                "salary_max": 150000,
                "salary_currency": "USD",
                "is_remote": True,
                "scam_score": 55,
            }
        )
        assert "Security Engineer" in text
        assert "Acme" in text
        assert "USD 100,000 - 150,000" in text
        assert "Remote Available" in text
        assert "Scam Score: 55" in text
        assert "Apply Here" in text

    def test_minimal_job(self):
        notifier = _ConcreteNotifier()
        text = notifier._format_job_alert({})
        assert "Unknown Position" in text
        assert "Unknown Company" in text
        assert "Remote" in text

    def test_low_scam_score_omitted(self):
        notifier = _ConcreteNotifier()
        text = notifier._format_job_alert({"scam_score": 10})
        assert "Scam Score" not in text


class TestFormatDailyDigest:
    def test_with_skills(self):
        notifier = _ConcreteNotifier()
        text = notifier._format_daily_digest(
            {
                "new_jobs": 12,
                "expiring_soon": 3,
                "top_skills": ["Python", "AWS", "Go", "K8s", "SQL", "Rust"],
            }
        )
        assert "12" in text
        assert "3" in text
        assert "Python" in text
        # only first 5 skills
        assert "Rust" not in text

    def test_minimal(self):
        notifier = _ConcreteNotifier()
        text = notifier._format_daily_digest({})
        assert "Daily CyberGuide Digest" in text
