"""Tests for the '🗓️ Interview soon' reminder sweep."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest


def _item(**overrides):
    item = {
        "application_id": "app-1",
        "job_id": "job-1",
        "job_title": "SOC Analyst",
        "company": "Acme Corp",
        "job_url": "https://acme.example/jobs/soc",
        "interview_at": datetime(2026, 8, 12, 14, 30),
        "location": "Bengaluru",
        "skills": ["Splunk", "SIEM", "Linux"],
    }
    item.update(overrides)
    return item


class TestInterviewReminderText:
    """The pure message/button builder."""

    def test_formats_title_time_skills_and_buttons(self):
        from interntrack.scheduler.jobs import _interview_reminder_text

        text, buttons = _interview_reminder_text(_item())
        assert "Interview soon" in text
        assert "SOC Analyst" in text
        assert "Acme Corp" in text
        assert "Wed 12 Aug · 02:30 PM (UTC)" in text
        assert "They expect: Splunk, SIEM, Linux" in text
        labels = [label for label, _ in buttons]
        assert "🔗 View job" in labels
        assert "📅 Add to calendar" in labels
        assert any("calendar.google.com" in url for _, url in buttons)

    def test_omits_buttons_without_url_and_empty_skills(self):
        from interntrack.scheduler.jobs import _interview_reminder_text

        text, buttons = _interview_reminder_text(
            _item(job_url="", skills=[], interview_at=None)
        )
        labels = [label for label, _ in buttons]
        assert "🔗 View job" not in labels
        assert "They expect" not in text
        # Calendar link is built from title/company and always present.
        assert "📅 Add to calendar" in labels


class TestInterviewRemindersFor:
    """The due-interview query mapping."""

    @pytest.mark.asyncio
    async def test_maps_and_sorts_by_interview_time(self):
        from interntrack.scheduler.jobs import _interview_reminders_for

        class _App:
            def __init__(self, app_id, interview_at):
                self.id = app_id
                self.job_id = f"job-{app_id}"
                self.user_id = "u1"
                self.interview_at = interview_at
                self.interview_reminder_sent_at = None

        class _Job:
            def __init__(self, jid, title, company, url, location, skills):
                self.id = jid
                self.title = title
                self.company = company
                self.url = url
                self.location = location
                self.required_skills = skills

        class _Result:
            def all(self):
                return [
                    (
                        _App("late", datetime(2026, 8, 12, 18, 0)),
                        _Job("job-late", "Late", "B", "", "", []),
                    ),
                    (
                        _App("early", datetime(2026, 8, 12, 9, 0)),
                        _Job(
                            "job-early",
                            "Early",
                            "A",
                            "https://a.example",
                            "Chennai",
                            ["Splunk"],
                        ),
                    ),
                ]

        class _Session:
            async def execute(self, stmt):
                return _Result()

        items = await _interview_reminders_for(_Session(), "u1")
        assert [i["application_id"] for i in items] == ["early", "late"]
        assert items[0]["job_title"] == "Early"
        assert items[0]["skills"] == ["Splunk"]

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        from interntrack.scheduler.jobs import _interview_reminders_for

        class _Boom:
            async def execute(self, stmt):
                raise RuntimeError("db down")

        assert await _interview_reminders_for(_Boom(), "u1") == []


class TestSendInterviewReminders:
    """The scheduled sweep end to end (mocked DB + channels)."""

    @pytest.mark.asyncio
    async def test_sends_once_and_marks_reminded(self, monkeypatch):
        from interntrack.scheduler.jobs import _send_interview_reminders

        calls = {"notify": [], "history": [], "commits": 0}

        class _FakeManager:
            def __init__(self, session):
                pass

            def get_configured_channels(self):
                return ["email"]

            async def notify(
                self, channels, message, subject=None, buttons=None, recipient=None
            ):
                calls["notify"].append((channels, message, subject, buttons, recipient))
                return {"email": True}

        async def _targets(session):
            return [{"user_id": "u1", "prefs": {"domains": ["security"]}, "user": None}]

        async def _items(session, user_id, hours=36):
            return [_item()]

        async def _history(session, **kwargs):
            calls["history"].append(kwargs)

        class _Session:
            async def execute(self, stmt):
                return AsyncMock()

            async def commit(self):
                calls["commits"] += 1

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets", _targets
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._interview_reminders_for", _items
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._record_alert_history", _history
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs.NotificationManager", _FakeManager
        )

        sent = await _send_interview_reminders(_Session())
        assert sent == {"u1": 1}
        assert len(calls["notify"]) == 1
        channels, message, subject, buttons, recipient = calls["notify"][0]
        assert subject == "🗓️ Interview soon"
        assert "SOC Analyst" in message
        assert len(buttons) == 2
        assert calls["history"][0]["subject"] == "🗓️ Interview soon"
        assert calls["history"][0]["job_count"] == 1
        # One commit per item, after the send + mark.
        assert calls["commits"] == 1

    @pytest.mark.asyncio
    async def test_skips_when_no_targets(self, monkeypatch):
        from interntrack.scheduler.jobs import _send_interview_reminders

        async def _no_targets(session):
            return []

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets", _no_targets
        )

        class _Session:
            pass

        assert await _send_interview_reminders(_Session()) == {}

    @pytest.mark.asyncio
    async def test_skips_paused_users(self, monkeypatch):
        from interntrack.scheduler.jobs import _send_interview_reminders

        async def _targets(session):
            future = datetime.now(UTC) + timedelta(days=2)
            return [
                {
                    "user_id": "u1",
                    "prefs": {"paused_until": future},
                    "user": None,
                }
            ]

        async def _items(session, user_id, hours=36):
            raise AssertionError("must not query for paused users")

        async def _history(session, **kwargs):
            raise AssertionError("must not record history for paused users")

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets", _targets
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._interview_reminders_for", _items
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._record_alert_history", _history
        )

        class _Session:
            pass

        assert await _send_interview_reminders(_Session()) == {}

    @pytest.mark.asyncio
    async def test_never_raises_on_inner_failure(self, monkeypatch):
        from interntrack.scheduler.jobs import _send_interview_reminders

        async def _boom_targets(session):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets", _boom_targets
        )

        class _Session:
            pass

        # Never raises even when the targets query explodes.
        assert await _send_interview_reminders(_Session()) == {}
