"""
Tests for multi-user daily alerts — per-user targets, per-user resume
scoping and per-user delivery routing.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEnabledAlertTargets:
    """_enabled_alert_targets lists every account with alerts on."""

    @pytest.mark.asyncio
    async def test_returns_registered_users_with_profiles(self, db_session):
        from interntrack.domain.models import AlertPreferences, User
        from interntrack.scheduler.jobs import _enabled_alert_targets

        user = User(name="Ada", email="ada@example.com", domains=["security"])
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            AlertPreferences(
                user_id=user.id,
                domains=["security"],
                channels=["email"],
                is_enabled=True,
            )
        )
        # Legacy user1 default + a disabled account.
        db_session.add(AlertPreferences(user_id="user1", is_enabled=True))
        db_session.add(AlertPreferences(user_id="disabled", is_enabled=False))
        await db_session.commit()

        targets = await _enabled_alert_targets(db_session)
        by_user = {t["user_id"]: t for t in targets}

        assert user.id in by_user
        assert by_user[user.id]["user"] is not None
        assert by_user[user.id]["user"].email == "ada@example.com"
        assert by_user[user.id]["prefs"]["domains"] == ["security"]
        # Legacy user1 has no profile object.
        assert by_user["user1"]["user"] is None
        # Disabled accounts are excluded.
        assert "disabled" not in by_user


class TestLatestResumeSkillNames:
    """_latest_resume_skill_names scopes the lookup to one user."""

    @pytest.mark.asyncio
    async def test_filters_by_user_id(self):
        from sqlalchemy import select

        from cybershield.domain.models import ResumeData
        from interntrack.scheduler.jobs import _latest_resume_skill_names

        # The where clause must reference user_id only when requested.
        assert select(ResumeData).whereclause is None
        filtered = select(ResumeData).where(ResumeData.user_id == "u-2")
        assert filtered.whereclause is not None
        assert "user_id" in str(filtered.whereclause)

        class FakeResume:
            skills = [{"name": "python"}]

        class FakeResult:
            def scalar_one_or_none(self):
                return FakeResume()

        class FakeSession:
            def __init__(self, query_capture):
                self.query_capture = query_capture

            async def execute(self, query, *args, **kwargs):
                self.query_capture.append(str(query))
                return FakeResult()

        captured = []
        skills = await _latest_resume_skill_names(FakeSession(captured), user_id="u-2")
        assert skills == {"python"}
        # The executed query filters resume rows by that user id.
        assert "resume_data.user_id" in captured[0]
        assert "WHERE" in captured[0]

    @pytest.mark.asyncio
    async def test_no_resume_returns_none(self):
        from interntrack.scheduler.jobs import _latest_resume_skill_names

        class EmptyResult:
            def scalar_one_or_none(self):
                return None

        class FakeSession:
            async def execute(self, *args, **kwargs):
                return EmptyResult()

        assert await _latest_resume_skill_names(FakeSession(), user_id="u-2") is None


class TestDeliverAlertRecipient:
    """_deliver_alert routes delivery + match scoring per user."""

    def _user(self, user_id="u-1", email="u@example.com", chat="777"):
        return SimpleNamespace(id=user_id, email=email, telegram_chat_id=chat)

    @pytest.mark.asyncio
    async def test_user_recipient_passed_to_notify(self):
        from interntrack.scheduler.jobs import _deliver_alert

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["email", "telegram"]
        manager.notify = AsyncMock(return_value={"email": True, "telegram": True})

        with (
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="msg"),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk", [("Apply", "https://x")])]),
            ),
        ):
            results = await _deliver_alert(
                manager,
                None,
                {"summary": {}, "new_jobs": []},
                AsyncMock(),
                user=self._user(),
            )

        assert results == {"email": True, "telegram": True}
        calls = manager.notify.call_args_list
        assert len(calls) == 2
        email_kwargs = calls[0].kwargs
        assert email_kwargs["recipient"] == {
            "email": "u@example.com",
            "telegram_chat_id": "777",
            "phone_number": None,
        }
        assert calls[1].kwargs["recipient"]["telegram_chat_id"] == "777"

    @pytest.mark.asyncio
    async def test_message_builders_get_user_id(self):
        from interntrack.scheduler.jobs import _deliver_alert

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["email"]
        manager.notify = AsyncMock(return_value={"email": True})
        build_message = AsyncMock(return_value="msg")

        with patch(
            "interntrack.scheduler.jobs.build_daily_report_html",
            new=build_message,
        ):
            await _deliver_alert(
                manager,
                None,
                {"summary": {}, "new_jobs": []},
                AsyncMock(),
                user=self._user("u-42"),
            )

        assert build_message.call_args.kwargs["user_id"] == "u-42"


class TestNotifyRecipientChannels:
    """NotificationManager.notify honors the per-user contact points."""

    @pytest.mark.asyncio
    async def test_email_to_user_and_telegram_to_user_chat(self):
        from interntrack.services.notification_service import NotificationManager

        with (
            patch("interntrack.services.notification_service.settings") as settings,
            patch(
                "interntrack.services.notification_service.EmailChannel"
            ) as email_cls,
            patch(
                "interntrack.services.notification_service.TelegramChannel"
            ) as tg_cls,
        ):
            settings.smtp_user = "sender@x.com"
            settings.smtp_password = "pw"
            settings.smtp_host = "smtp.example.com"
            settings.smtp_port = 587
            settings.email_from = "noreply@x.com"
            settings.telegram_bot_token = "bot-token"
            settings.telegram_chat_id = "shared-chat"
            email_cls.return_value.send = AsyncMock(return_value=True)
            tg_cls.return_value.send = AsyncMock(return_value=True)

            manager = NotificationManager(AsyncMock())
            results = await manager.notify(
                ["email", "telegram"],
                "hello",
                recipient={"email": "user@example.com", "telegram_chat_id": "999"},
            )

        assert results == {"email": True, "telegram": True}
        assert email_cls.call_args.kwargs["to_email"] == "user@example.com"
        assert tg_cls.call_args.args[1] == "999"


class TestGenerateDailyReportMultiUser:
    """generate_daily_report delivers a personalized digest per user."""

    @pytest.mark.asyncio
    async def test_sends_to_every_enabled_user(self):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        targets = [
            {
                "user_id": "u1",
                "prefs": {
                    "is_enabled": True,
                    "domains": ["security"],
                    "channels": ["email"],
                    "min_match_score": None,
                    "last_alert_at": None,
                },
                "user": SimpleNamespace(
                    id="u1", email="a@example.com", telegram_chat_id=None
                ),
            },
            {
                "user_id": "u2",
                "prefs": {
                    "is_enabled": True,
                    "domains": ["coding"],
                    "channels": ["telegram"],
                    "min_match_score": None,
                    "last_alert_at": None,
                },
                "user": SimpleNamespace(
                    id="u2", email="b@example.com", telegram_chat_id="9"
                ),
            },
        ]

        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch(
                "interntrack.scheduler.jobs._enabled_alert_targets",
                new=AsyncMock(return_value=targets),
            ),
            patch("interntrack.scheduler.jobs.ReportService") as report_cls,
            patch("interntrack.scheduler.jobs.NotificationManager"),
            patch(
                "interntrack.scheduler.jobs._deliver_alert",
                new=AsyncMock(return_value={"email": True}),
            ) as deliver,
            patch("interntrack.scheduler.jobs._mark_alert_sent", new=AsyncMock()),
            patch("interntrack.scheduler.jobs._record_alert_history", new=AsyncMock()),
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)
            report_cls.return_value.generate_daily_report = AsyncMock(
                return_value={"summary": {"new_jobs": 1}, "new_jobs": [{}]}
            )

            await generate_daily_report()

        assert deliver.await_count == 2
        users = [call.kwargs["user"].id for call in deliver.call_args_list]
        assert users == ["u1", "u2"]

    @pytest.mark.asyncio
    async def test_disabled_user_skipped_in_loop(self):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        targets = [
            {
                "user_id": "off",
                "prefs": {"is_enabled": False, "domains": [], "channels": []},
                "user": SimpleNamespace(id="off", email=None, telegram_chat_id=None),
            }
        ]
        with (
            patch("interntrack.scheduler.jobs.get_db_session") as mock_db,
            patch(
                "interntrack.scheduler.jobs._enabled_alert_targets",
                new=AsyncMock(return_value=targets),
            ),
            patch(
                "interntrack.scheduler.jobs._deliver_alert", new=AsyncMock()
            ) as deliver,
        ):
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)
            await generate_daily_report()

        deliver.assert_not_awaited()


class TestSendAlertForLocation:
    """The per-user digest is scoped to each account's own city."""

    @pytest.mark.asyncio
    async def test_digest_scoped_to_user_location(self):
        from interntrack.scheduler.jobs import _send_alert_for

        fake_user = SimpleNamespace(
            id="u1",
            location="Chennai",
            email="friend@example.com",
            telegram_chat_id=None,
        )
        prefs = {"domains": ["frontend"], "channels": ["email"], "min_match_score": 0}
        mock_session = AsyncMock()
        mock_service = AsyncMock()
        mock_service.generate_daily_report.return_value = {
            "new_jobs": [{"title": "React Dev", "company": "Acme"}],
        }

        with (
            patch(
                "interntrack.scheduler.jobs.ReportService",
                return_value=mock_service,
            ),
            patch("interntrack.scheduler.jobs._mark_alert_sent", new=AsyncMock()),
            patch(
                "interntrack.scheduler.jobs._deliver_alert", new=AsyncMock()
            ) as deliver,
            patch("interntrack.scheduler.jobs._record_alert_history", new=AsyncMock()),
            patch("interntrack.scheduler.jobs.NotificationManager"),
        ):
            await _send_alert_for(mock_session, "u1", prefs, fake_user)

        kwargs = mock_service.generate_daily_report.call_args.kwargs
        assert kwargs.get("location") == "Chennai"
        assert kwargs.get("domains") == ["frontend"]
        # Delivery routes to the user's own profile.
        assert deliver.call_args.kwargs.get("user") is fake_user

    @pytest.mark.asyncio
    async def test_no_user_no_location_filter(self):
        """Legacy user1 path (no profile) falls back to DEFAULT_LOCATION.

        The default user has no profile row, so their digest is scoped to
        the shared default city (Bangalore) + remote/WFH, never every-city.
        """
        from interntrack.scheduler.jobs import DEFAULT_LOCATION, _send_alert_for

        prefs = {"domains": None, "channels": None, "min_match_score": None}
        mock_session = AsyncMock()
        mock_service = AsyncMock()
        mock_service.generate_daily_report.return_value = {
            "new_jobs": [{"title": "Job", "company": "X"}],
        }

        with (
            patch(
                "interntrack.scheduler.jobs.ReportService",
                return_value=mock_service,
            ),
            patch("interntrack.scheduler.jobs._mark_alert_sent", new=AsyncMock()),
            patch(
                "interntrack.scheduler.jobs._deliver_alert",
                new=AsyncMock(return_value={"email": True}),
            ),
            patch("interntrack.scheduler.jobs._record_alert_history", new=AsyncMock()),
            patch("interntrack.scheduler.jobs.NotificationManager"),
        ):
            await _send_alert_for(mock_session, "user1", prefs, None)

        assert (
            mock_service.generate_daily_report.call_args.kwargs.get("location")
            == DEFAULT_LOCATION
        )
        assert (
            mock_service.generate_daily_report.call_args.kwargs.get("include_remote")
            is True
        )
