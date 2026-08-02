"""
Tests for NotificationOrchestrator.

Covers channel registration, single/multi/all sends, job/scam/digest/report
notification builders, formatting helpers, stats, and the default-orchestrator
factory — using async mocks for channels (no real network).
"""

from unittest.mock import AsyncMock, patch

import pytest

from cybershield.notifications.base import (
    NotificationMessage,
    NotificationPriority,
    NotificationType,
)
from cybershield.notifications.orchestrator import (
    NotificationOrchestrator,
    create_default_orchestrator,
)


class _FakeChannel:
    """Minimal BaseNotifier stand-in recording send_safe calls."""

    def __init__(self, name: str, enabled: bool = True, success: bool = True):
        self.name = name
        self.enabled = enabled
        self.success = success
        self.sent: list[NotificationMessage] = []

    async def send_safe(self, message: NotificationMessage) -> bool:
        """Record the message and return the scripted success value."""
        self.sent.append(message)
        return self.success


@pytest.fixture
def orchestrator():
    return NotificationOrchestrator()


@pytest.fixture
def channels():
    return {
        "telegram": _FakeChannel("telegram"),
        "email": _FakeChannel("email", success=False),
        "disabled": _FakeChannel("disabled", enabled=False),
    }


def _register(orchestrator, channels):
    for name, channel in channels.items():
        orchestrator.register(name, channel)


class TestChannelManagement:
    def test_register_and_list(self, orchestrator):
        ch = _FakeChannel("telegram")
        orchestrator.register("telegram", ch)
        assert orchestrator.list_channels() == ["telegram"]
        assert orchestrator.get_channel("telegram") is ch
        assert orchestrator.get_channel("missing") is None

    def test_register_initializes_stats(self, orchestrator):
        orchestrator.register("email", _FakeChannel("email"))
        assert orchestrator._stats["email"] == {"sent": 0, "failed": 0}

    def test_unregister(self, orchestrator):
        ch = _FakeChannel("telegram")
        orchestrator.register("telegram", ch)
        orchestrator.unregister("telegram")
        assert orchestrator.get_channel("telegram") is None
        assert "telegram" not in orchestrator._stats

    def test_unregister_missing_is_noop(self, orchestrator):
        orchestrator.unregister("nope")  # should not raise

    def test_get_enabled_channels(self, orchestrator, channels):
        _register(orchestrator, channels)
        enabled = orchestrator.get_enabled_channels()
        assert "telegram" in enabled
        assert "email" in enabled
        assert "disabled" not in enabled


class TestSendPaths:
    @pytest.mark.asyncio
    async def test_send_to_channel_missing_returns_false(self, orchestrator):
        assert await orchestrator.send_to_channel("nope", _message()) is False

    @pytest.mark.asyncio
    async def test_send_to_channel_success_updates_stats(self, orchestrator, channels):
        _register(orchestrator, channels)
        ok = await orchestrator.send_to_channel("telegram", _message())
        assert ok is True
        assert orchestrator._stats["telegram"] == {"sent": 1, "failed": 0}

    @pytest.mark.asyncio
    async def test_send_to_channel_failure_updates_stats(self, orchestrator, channels):
        _register(orchestrator, channels)
        ok = await orchestrator.send_to_channel("email", _message())
        assert ok is False
        assert orchestrator._stats["email"] == {"sent": 0, "failed": 1}

    @pytest.mark.asyncio
    async def test_send_to_channels_gathers_results(self, orchestrator, channels):
        _register(orchestrator, channels)
        results = await orchestrator.send_to_channels(["telegram", "email"], _message())
        assert results == {"telegram": True, "email": False}

    @pytest.mark.asyncio
    async def test_send_to_channels_handles_exception(self, orchestrator):
        ch = _FakeChannel("telegram")
        with patch.object(ch, "send_safe", AsyncMock(side_effect=RuntimeError("boom"))):
            orchestrator.register("telegram", ch)
            results = await orchestrator.send_to_channels(["telegram"], _message())
        assert results == {"telegram": False}

    @pytest.mark.asyncio
    async def test_send_to_all_respects_enabled_and_exclude(self, orchestrator, channels):
        _register(orchestrator, channels)
        results = await orchestrator.send_to_all(_message(), exclude=["email"])
        assert list(results.keys()) == ["telegram"]


class TestNotificationBuilders:
    @pytest.mark.asyncio
    async def test_send_job_alert_to_channels(self, orchestrator, channels):
        _register(orchestrator, channels)
        job = {
            "title": "Security Analyst",
            "company_name": "Acme",
            "location": "Remote",
            "source": "linkedin",
            "url": "https://job.example/1",
        }
        results = await orchestrator.send_job_alert(job, channels=["telegram"])
        assert results == {"telegram": True}
        sent: NotificationMessage = channels["telegram"].sent[0]
        assert sent.notification_type == NotificationType.WATCHLIST_MATCH
        assert sent.priority == NotificationPriority.HIGH

    @pytest.mark.asyncio
    async def test_send_job_alert_to_all(self, orchestrator, channels):
        _register(orchestrator, channels)
        job = {"title": "Analyst", "company_name": "Acme"}
        results = await orchestrator.send_job_alert(job)
        # disabled channel skipped
        assert set(results.keys()) == {"telegram", "email"}

    @pytest.mark.asyncio
    async def test_send_scam_alert_excludes_telegram_by_default(self, orchestrator, channels):
        _register(orchestrator, channels)
        results = await orchestrator.send_scam_alert(
            {"title": "Scam Job", "company_name": "Fake"}, 88.0
        )
        assert "telegram" not in results
        assert "email" in results

    @pytest.mark.asyncio
    async def test_send_daily_digest(self, orchestrator, channels):
        _register(orchestrator, channels)
        results = await orchestrator.send_daily_digest(
            {"new_jobs": 5, "expiring_soon": 2, "high_match": 1},
            channels=["telegram"],
        )
        assert results == {"telegram": True}
        sent: NotificationMessage = channels["telegram"].sent[0]
        assert sent.notification_type == NotificationType.DAILY_DIGEST

    @pytest.mark.asyncio
    async def test_send_report_types(self, orchestrator, channels):
        _register(orchestrator, channels)
        data = {"title": "Weekly", "new_jobs": 10, "period": "2026-W31"}
        results = await orchestrator.send_report("weekly", data, channels=["telegram"])
        assert results == {"telegram": True}
        sent: NotificationMessage = channels["telegram"].sent[0]
        assert sent.notification_type == NotificationType.WEEKLY_REPORT
        assert sent.priority == NotificationPriority.LOW

    @pytest.mark.asyncio
    async def test_send_report_monthly_priority(self, orchestrator, channels):
        _register(orchestrator, channels)
        await orchestrator.send_report("monthly", {"new_jobs": 1}, channels=["telegram"])
        sent: NotificationMessage = channels["telegram"].sent[0]
        assert sent.priority == NotificationPriority.MEDIUM


class TestFormatting:
    def test_format_job_content_with_all_fields(self, orchestrator):
        content = orchestrator._format_job_content(
            {
                "title": "Analyst",
                "company_name": "Acme",
                "location": "NYC",
                "salary_min": 80000,
                "salary_max": 120000,
                "salary_currency": "USD",
                "is_remote": True,
                "required_skills": ["Python", "SIEM", "AWS", "K8s", "Go", "Rust"],
            }
        )
        assert "Analyst" in content
        assert "USD 80,000 - 120,000" in content
        assert "Remote Available" in content
        assert "Python" in content
        # only first 5 skills listed
        assert "Rust" not in content

    def test_format_job_content_minimal(self, orchestrator):
        content = orchestrator._format_job_content({})
        assert "Unknown Position" in content
        assert "Unknown Company" in content
        assert "Remote" in content

    def test_format_daily_digest_with_skills_and_companies(self, orchestrator):
        content = orchestrator._format_daily_digest(
            {
                "new_jobs": 7,
                "expiring_soon": 1,
                "high_match": 3,
                "top_skills": ["Python", "AWS", "Go", "K8s", "SQL", "React"],
                "top_companies": ["Acme", "Beta"],
            }
        )
        assert "7" in content
        assert "Python" in content
        assert "Acme" in content

    def test_format_daily_digest_minimal(self, orchestrator):
        content = orchestrator._format_daily_digest({})
        assert "0" in content

    def test_format_report_full(self, orchestrator):
        content = orchestrator._format_report(
            {
                "period": "2026-W31",
                "new_jobs": 5,
                "total_jobs": 100,
                "applications_submitted": 10,
                "success_rate": 30,
                "expiring_soon": 2,
                "expiring_next_week": 4,
                "avg_salary_range": "$80k-$120k",
                "remote_percentage": 60,
                "top_companies": [("Acme", 5), ("Beta", 3)],
                "top_skills": ["Python", "AWS"],
                "job_types": [("full_time", 80), ("internship", 20)],
            }
        )
        assert "Period:" in content
        assert "Acme (5)" in content
        assert "full_time (80)" in content
        assert "60%" in content

    def test_format_report_minimal(self, orchestrator):
        assert orchestrator._format_report({}) == ""


class TestStatsAndFactory:
    def test_get_stats(self, orchestrator, channels):
        _register(orchestrator, channels)
        stats = orchestrator.get_stats()
        assert "telegram" in stats["channels"]
        assert "email" in stats["enabled"]
        assert stats["stats"]["telegram"] == {"sent": 0, "failed": 0}

    def test_create_default_orchestrator_all_channels(self):
        orch = create_default_orchestrator(
            {
                "telegram": {"bot_token": "t", "chat_id": "c"},
                "email": {"smtp_host": "smtp.test"},
                "discord": {"webhook_url": "https://d"},
                "slack": {"webhook_url": "https://s"},
            }
        )
        assert set(orch.list_channels()) == {"telegram", "email", "discord", "slack"}

    def test_create_default_orchestrator_empty(self):
        orch = create_default_orchestrator({})
        assert orch.list_channels() == []


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
