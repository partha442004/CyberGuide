"""Unit tests for scheduler/jobs.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFormatDailyReport:
    """Tests for format_daily_report function."""

    def test_format_daily_report_basic(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {
            "summary": {
                "new_jobs": 5,
                "new_applications": 3,
                "total_applications": 10,
            },
        }

        result = format_daily_report(report)

        assert "📊 Daily Report" in result
        assert "New Jobs: 5" in result
        assert "New Applications: 3" in result
        assert "Total Applications: 10" in result

    def test_format_daily_report_empty(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {}
        result = format_daily_report(report)

        assert "📊 Daily Report" in result
        assert "New Jobs: 0" in result
        assert "New Applications: 0" in result
        assert "Total Applications: 0" in result

    def test_format_daily_report_missing_summary(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {"other_key": "value"}
        result = format_daily_report(report)

        assert "New Jobs: 0" in result

    def test_format_daily_report_partial_summary(self):
        from interntrack.scheduler.jobs import format_daily_report

        report = {"summary": {"new_jobs": 10}}
        result = format_daily_report(report)

        assert "New Jobs: 10" in result
        assert "New Applications: 0" in result
        assert "Total Applications: 0" in result


class TestBuildDailyReportMessage:
    """Tests for the rich daily-report message (links + match %)."""

    @pytest.mark.asyncio
    async def test_includes_job_links_and_match_percent(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security", "python"],
                }
            ],
        }

        class FakeResume:
            skills = [{"name": "Python", "category": "scripting"}]

        class FakeResult:
            def scalar_one_or_none(self):
                return FakeResume()

        class FakeSession:
            async def execute(self, *args, **kwargs):
                return FakeResult()

        message = await build_daily_report_message(report, FakeSession())

        assert "Security Engineer" in message
        assert "Acme Corp" in message
        assert "Apply" in message
        assert "https://acme.example/apply" in message
        assert "%" in message

    @pytest.mark.asyncio
    async def test_no_jobs_keeps_summary_only(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {"summary": {"new_jobs": 0, "new_applications": 0}}
        message = await build_daily_report_message(report, None)
        assert "New Jobs: 0" in message
        assert "Apply" not in message

    @pytest.mark.asyncio
    async def test_groups_jobs_by_domain_sections(self):
        """Jobs are grouped into domain sections with age badges."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 3, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "title": "SOC Analyst",
                    "company": "SecureCo",
                    "url": "https://a/apply",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": True,
                },
                {
                    "title": "Python Developer",
                    "company": "TechCo",
                    "url": "https://b/apply",
                    "age_days": 1,
                    "domain": "coding",
                    "is_applied": False,
                },
                {
                    "title": "Old Job",
                    "company": "C",
                    "url": "https://c/apply",
                    "age_days": 5,
                    "domain": "security",
                    "is_applied": False,
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "Cybersecurity / VAPT / SOC (2)" in message
        assert "Coding / Software (1)" in message
        assert "SOC Analyst" in message
        assert "Python Developer" in message
        assert "✅ Applied" in message
        assert "⬜ Not applied" in message
        assert "🟢 today" in message
        assert "🟡 1d ago" in message
        assert "⚪ 5d ago" in message

    @pytest.mark.asyncio
    async def test_expiry_badges_in_message(self):
        """Closing-soon and expired jobs get visible badges."""
        from datetime import UTC, datetime, timedelta

        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 2, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "title": "Closing Job",
                    "company": "A",
                    "url": "https://a/apply",
                    "age_days": 0,
                    "is_active": True,
                    "expires_at": ((datetime.now(UTC) + timedelta(days=1)).isoformat()),
                },
                {
                    "title": "Dead Job",
                    "company": "B",
                    "url": "https://b/apply",
                    "age_days": 0,
                    "is_active": False,
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "Closing soon" in message
        assert "Expired / closed" in message

    def test_expiry_note(self):
        from datetime import UTC, datetime, timedelta

        from interntrack.scheduler.jobs import _expiry_note

        assert _expiry_note({"is_active": False}) == "   ❌ Expired / closed"
        assert _expiry_note({"is_active": True}) == ""
        assert "Closing soon" in _expiry_note(
            {
                "is_active": True,
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        )
        assert "Expired" in _expiry_note(
            {
                "is_active": True,
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )

    @pytest.mark.asyncio
    async def test_closing_soon_section_in_message(self):
        """Deadline jobs lead the daily digest so they aren't missed."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [],
            "closing_soon": [
                {
                    "title": "VAPT Intern",
                    "company": "SecureCo",
                    "expires_at": "2026-08-09T00:00:00",
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "🚨 Closing soon (1):" in message
        assert "VAPT Intern" in message
        assert "SecureCo" in message

    @pytest.mark.asyncio
    async def test_follow_up_section_in_message(self):
        """Pending applications appear as follow-up nudges in the digest."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 0, "new_applications": 0, "total_applications": 2},
            "new_jobs": [],
            "follow_up": [
                {
                    "application_id": "app-1",
                    "status": "applied",
                    "job_title": "SOC Analyst",
                    "company": "Zscaler",
                    "applied_at": "2026-08-05T00:00:00",
                },
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "⏰ Follow up (1):" in message
        assert "SOC Analyst" in message
        assert "Zscaler" in message

    def test_salary_txt(self):
        from interntrack.scheduler.jobs import _salary_txt

        assert _salary_txt({}) == ""
        assert (
            _salary_txt({"salary_min": 100000, "salary_max": 150000}) == "$100k–$150k"
        )
        assert _salary_txt({"salary_min": 600000, "salary_currency": "INR"}) == "₹6L"
        assert _salary_txt({"salary_max": 25000, "salary_currency": "INR"}) == "₹25K"

    def test_age_badge(self):
        from interntrack.scheduler.jobs import _age_badge

        assert _age_badge(0) == "🟢 today"
        assert _age_badge(1) == "🟡 1d ago"
        assert _age_badge(2) == "🟠 2d ago"
        assert _age_badge(7) == "⚪ 7d ago"


class TestTeamDigestStats:
    """_team_digest_stats computes the weekly email team snapshot."""

    class FakeUser:
        def __init__(self, email, referred_by=None):
            self.email = email
            self.referred_by = referred_by

    class FakeSession:
        def __init__(self, users):
            self._users = users

        async def execute(self, *args, **kwargs):
            class Result:
                def __init__(self, users):
                    self._users = users

                def scalars(self):
                    return self

                def all(self):
                    return self._users

            return Result(self._users)

    @pytest.mark.asyncio
    async def test_counts_team_and_my_referrals(self):
        from interntrack.scheduler.jobs import _team_digest_stats

        session = self.FakeSession(
            [
                self.FakeUser("me@x.com"),
                self.FakeUser("friend@x.com", referred_by="me@x.com"),
                self.FakeUser("other@x.com", referred_by="someone@x.com"),
            ]
        )
        stats = await _team_digest_stats(session, email="me@x.com")
        assert stats == {"team_size": 3, "my_referrals": 1}

    @pytest.mark.asyncio
    async def test_case_insensitive_and_self_excluded(self):
        from interntrack.scheduler.jobs import _team_digest_stats

        session = self.FakeSession(
            [
                self.FakeUser("me@x.com", referred_by="ME@x.com"),  # self-referral
                self.FakeUser("f@x.com", referred_by="Me@X.COM"),
            ]
        )
        stats = await _team_digest_stats(session, email="me@x.com")
        assert stats == {"team_size": 2, "my_referrals": 1}

    @pytest.mark.asyncio
    async def test_no_users_returns_none(self):
        from interntrack.scheduler.jobs import _team_digest_stats

        stats = await _team_digest_stats(self.FakeSession([]), email="me@x.com")
        assert stats is None


class TestBuildAlertChunks:
    """Tests for the Telegram chunk builder (email-parity layout)."""

    def _report(self, jobs: list[dict]) -> dict:
        return {
            "summary": {
                "new_jobs": len(jobs),
                "new_applications": 0,
                "total_applications": 0,
            },
            "new_jobs": jobs,
            "closing_soon": [],
            "follow_up": [],
        }

    @pytest.mark.asyncio
    async def test_location_split_puts_bangalore_first(self):
        """With a Bangalore user, local jobs lead and others get a banner."""
        from interntrack.scheduler.jobs import build_alert_chunks

        report = self._report(
            [
                {
                    "title": "SOC Analyst",
                    "company": "SecureCo",
                    "url": "https://a/apply",
                    "location": "Bengaluru, Karnataka, India",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": False,
                },
                {
                    "title": "Security Engineer",
                    "company": "OtherCo",
                    "url": "https://b/apply",
                    "location": "Hyderabad, Telangana, India",
                    "age_days": 1,
                    "domain": "security",
                    "is_applied": False,
                },
            ],
        )

        chunks = await build_alert_chunks(
            report,
            None,
            user_location="Bangalore",
        )

        joined = "\n".join(text for text, _buttons in chunks)
        # Your area banner present and the breakdown table closes the digest.
        assert "Your area (Bangalore)" in joined
        assert "Other locations" in joined
        assert "Jobs by role × location" in joined
        # Local job has an Apply button; every job keeps its link.
        all_buttons = [b for _t, bs in chunks for b in bs]
        assert any("SOC Analyst" in label for label, _u in all_buttons)

    @pytest.mark.asyncio
    async def test_no_location_no_split(self):
        """Without a user location everything is one section, no banners."""
        from interntrack.scheduler.jobs import build_alert_chunks

        report = self._report(
            [
                {
                    "title": "Security Engineer",
                    "company": "Acme",
                    "url": "https://a/apply",
                    "location": "Remote",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": False,
                },
            ],
        )

        chunks = await build_alert_chunks(report, None, user_location=None)
        joined = "\n".join(text for text, _b in chunks)

        assert "Your area" not in joined
        assert "Other locations" not in joined
        assert "Security Engineer" in joined

    @pytest.mark.asyncio
    async def test_empty_report_single_summary_chunk(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        chunks = await build_alert_chunks(self._report([]), None)
        assert len(chunks) == 1
        assert "New Jobs: 0" in chunks[0][0]

    def test_telegram_breakdown_table(self):
        """The breakdown renders a role × location HTML table."""
        from interntrack.scheduler.jobs import _telegram_breakdown

        here = [
            (
                "security",
                80.0,
                {"title": "A", "domain": "security", "location": "Bengaluru"},
            ),
            (
                "security",
                90.0,
                {"title": "B", "domain": "security", "location": "Bengaluru"},
            ),
        ]
        there = [
            ("coding", 50.0, {"title": "C", "domain": "coding", "location": "Mumbai"})
        ]

        html = _telegram_breakdown(here, there)

        assert "Jobs by role × location" in html
        assert "<table" in html
        assert "Security" in html
        assert "Coding" in html
        assert "Bengaluru" in html
        assert "Mumbai" in html


class TestDeliverAlertLocationFallback:
    """The digest location split falls back to the default location."""

    @pytest.mark.asyncio
    async def test_location_split_works_without_user_profile(self):
        """Legacy user1 path (no profile) still gets the Bangalore split."""
        from interntrack.scheduler.jobs import DEFAULT_LOCATION, _deliver_alert

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "title": "SOC Analyst",
                    "company": "SecureCo",
                    "url": "https://a/apply",
                    "location": "Bengaluru, Karnataka, India",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": False,
                },
            ],
            "closing_soon": [],
            "follow_up": [],
        }

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["telegram"]
        manager.notify = AsyncMock(return_value={"telegram": True})

        with (
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(
                    return_value=[("chunk-with-jobs", [("Apply", "https://a")])]
                ),
            ) as mock_chunks,
        ):
            results = await _deliver_alert(manager, ["telegram"], report, None)

        assert results.get("telegram") is True
        # The builders must receive the default location so the split renders.
        call_kwargs = mock_chunks.call_args.kwargs
        assert call_kwargs.get("user_location") == DEFAULT_LOCATION
        assert call_kwargs.get("user_location") == "Bangalore"

    @pytest.mark.asyncio
    async def test_user_location_wins_over_default(self):
        """A profile location overrides the default fallback."""
        from interntrack.scheduler.jobs import _deliver_alert

        report = {
            "summary": {"new_jobs": 0, "new_applications": 0, "total_applications": 0},
            "new_jobs": [],
            "closing_soon": [],
            "follow_up": [],
        }

        class FakeUser:
            id = "u2"
            email = "a@b.c"
            telegram_chat_id = "42"
            location = "Chennai"

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["telegram"]
        manager.notify = AsyncMock(return_value={"telegram": True})

        with patch(
            "interntrack.scheduler.jobs.build_alert_chunks",
            new=AsyncMock(return_value=[("chunk", [])]),
        ) as mock_chunks:
            await _deliver_alert(manager, ["telegram"], report, None, user=FakeUser())

        call_kwargs = mock_chunks.call_args.kwargs
        assert call_kwargs.get("user_location") == "Chennai"

    @pytest.mark.asyncio
    async def test_digest_skips_telegram_when_instant_alerts_on(self):
        """Instant-alert users get one Telegram message (instant), not two."""
        from interntrack.scheduler.jobs import _deliver_alert

        report = {
            "summary": {"new_jobs": 0, "new_applications": 0, "total_applications": 0},
            "new_jobs": [],
            "closing_soon": [],
            "follow_up": [],
        }

        class FakeUser:
            id = "u3"
            email = "c@d.e"
            telegram_chat_id = "99"
            location = "Bangalore"

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["telegram", "email"]

        async def _fake_notify(channels, *args, **kwargs):
            return dict.fromkeys(channels, True)

        manager.notify = AsyncMock(side_effect=_fake_notify)

        with patch(
            "interntrack.scheduler.jobs._load_alert_preferences",
            new=AsyncMock(
                return_value={"instant_alerts": True, "domains": [], "channels": []}
            ),
        ):
            results = await _deliver_alert(
                manager,
                ["telegram", "email"],
                report,
                None,
                user=FakeUser(),
            )

        # Telegram chunks must NOT be built/sent for instant-alert users.
        assert "telegram" not in results
        # The email digest still delivers.
        assert results.get("email") is True

    @pytest.mark.asyncio
    async def test_digest_keeps_telegram_when_instant_alerts_off(self):
        """Users who turned instant alerts off still get Telegram digest chunks."""
        from interntrack.scheduler.jobs import _deliver_alert

        report = {
            "summary": {"new_jobs": 0, "new_applications": 0, "total_applications": 0},
            "new_jobs": [],
            "closing_soon": [],
            "follow_up": [],
        }

        class FakeUser:
            id = "u4"
            email = "e@f.g"
            telegram_chat_id = "77"
            location = "Bangalore"

        manager = MagicMock()
        manager.get_configured_channels.return_value = ["telegram"]
        manager.notify = AsyncMock(return_value={"telegram": True})

        with (
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "instant_alerts": False,
                        "domains": [],
                        "channels": [],
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk", [])]),
            ),
        ):
            results = await _deliver_alert(
                manager,
                ["telegram"],
                report,
                None,
                user=FakeUser(),
            )

        assert results.get("telegram") is True


@pytest.mark.asyncio
class TestRunJobDiscovery:
    """Tests for run_job_discovery async function."""

    @patch("interntrack.scrapers.registry.get_default_registry")
    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_run_job_discovery_success(
        self,
        mock_get_db,
        mock_service_cls,
        mock_registry_fn,
    ):
        from interntrack.scheduler.jobs import run_job_discovery

        # Setup mocks
        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_registry = AsyncMock()
        mock_registry.fetch_all.return_value = [
            {"title": "Python Dev", "company": "TechCo"},
        ]
        mock_registry_fn.return_value = mock_registry

        mock_service = AsyncMock()
        mock_service.save_jobs.return_value = [{"title": "Python Dev"}]
        mock_service_cls.return_value = mock_service

        # Run
        await run_job_discovery()

        # Verify
        mock_registry.fetch_all.assert_called_once()
        mock_service.save_jobs.assert_called_once_with(
            [{"title": "Python Dev", "company": "TechCo"}],
        )

    @patch("interntrack.scrapers.registry.get_default_registry")
    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_run_job_discovery_no_jobs(
        self,
        mock_get_db,
        mock_service_cls,
        mock_registry_fn,
    ):
        from interntrack.scheduler.jobs import run_job_discovery

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_registry = AsyncMock()
        mock_registry.fetch_all.return_value = []
        mock_registry_fn.return_value = mock_registry

        mock_service = AsyncMock()
        mock_service.save_jobs.return_value = []
        mock_service_cls.return_value = mock_service

        await run_job_discovery()

        mock_registry.fetch_all.assert_called_once()
        mock_service.save_jobs.assert_called_with([])

    """Tests for generate_daily_report async function."""


class TestGenerateDailyReport:
    """Tests for generate_daily_report async function."""

    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch("interntrack.scheduler.jobs.ReportService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    @pytest.mark.asyncio
    async def test_generate_daily_report_success(
        self,
        mock_get_db,
        mock_report_cls,
        mock_notif_cls,
    ):
        from interntrack.scheduler.jobs import generate_daily_report

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_report_service = AsyncMock()
        mock_report_service.generate_daily_report.return_value = {
            "summary": {"new_jobs": 5, "new_applications": 3, "total_applications": 10},
            "new_jobs": [{}],
        }
        mock_report_cls.return_value = mock_report_service

        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["telegram"]
        mock_manager.notify = AsyncMock(return_value={"telegram": True})
        mock_notif_cls.return_value = mock_manager

        with (
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": [],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": True,
                        "last_alert_at": None,
                        "slot_domains": {},
                        "weekly_enabled": True,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs.build_alert_chunks",
                new=AsyncMock(return_value=[("chunk", [("Apply", "https://x")])]),
            ),
        ):
            await generate_daily_report()

        mock_report_service.generate_daily_report.assert_called_once()
        mock_manager.notify.assert_awaited_once_with(
            ["telegram"],
            "chunk",
            subject="Daily Report",
            buttons=[("Apply", "https://x")],
        )

    @patch("interntrack.engines.verification.VerificationEngine")
    @patch("interntrack.scheduler.jobs.get_db_session")
    async def test_verify_job_links(self, mock_get_db, mock_engine_cls):
        from interntrack.scheduler.jobs import verify_job_links

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_engine = AsyncMock()
        mock_engine.verify_all_links.return_value = [
            {"url": "http://alive.com", "is_alive": True},
            {"url": "http://dead.com", "is_alive": False},
        ]
        mock_engine_cls.return_value = mock_engine

        await verify_job_links()

        mock_engine.verify_all_links.assert_called_once()

    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    @pytest.mark.asyncio
    async def test_deactivate_expired_jobs(self, mock_get_db, mock_service_cls):
        from interntrack.scheduler.jobs import deactivate_expired_jobs

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_service = AsyncMock()
        mock_service.deactivate_expired.return_value = 3
        mock_service_cls.return_value = mock_service

        await deactivate_expired_jobs()

        mock_service.deactivate_expired.assert_called_once()

    @patch("interntrack.scheduler.jobs.JobService")
    @patch("interntrack.scheduler.jobs.get_db_session")
    @pytest.mark.asyncio
    async def test_deactivate_expired_jobs_none(self, mock_get_db, mock_service_cls):
        from interntrack.scheduler.jobs import deactivate_expired_jobs

        mock_session = AsyncMock()
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        mock_service = AsyncMock()
        mock_service.deactivate_expired.return_value = 0
        mock_service_cls.return_value = mock_service

        await deactivate_expired_jobs()

        mock_service.deactivate_expired.assert_called_once()


class TestSendInstantAlerts:
    """Tests for _send_instant_alerts async function."""

    def _job(self, **overrides) -> MagicMock:
        job = MagicMock()
        job.id = overrides.get("id", "job-1")
        job.title = overrides.get("title", "SOC Analyst")
        job.company = overrides.get("company", "Cyber Corp")
        job.location = overrides.get("location", "Bangalore")
        job.url = overrides.get("url", "https://example.com/job")
        job.tags = overrides.get("tags", ["security", "soc"])
        job.required_skills = overrides.get("required_skills", [])
        job.preferred_skills = overrides.get("preferred_skills", [])
        return job

    @patch("interntrack.scheduler.jobs._job_match_score")
    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch(
        "interntrack.scheduler.jobs._latest_resume_skill_names",
        new_callable=AsyncMock,
    )
    async def test_sends_telegram_ping_for_matching_job(
        self,
        mock_resume,
        mock_manager_cls,
        mock_match,
    ):
        from interntrack.scheduler.jobs import _send_instant_alerts

        mock_resume.return_value = {"python", "linux"}
        mock_match.return_value = 75.0
        session = AsyncMock()
        user = MagicMock()
        user.id = "user-1"
        user.telegram_chat_id = "123456"
        user.location = "Bangalore"
        mock_targets = [
            {
                "user_id": "user-1",
                "user": user,
                "prefs": {
                    "instant_alerts": True,
                    "domains": ["security"],
                    "min_match_score": 40,
                },
            },
        ]
        mock_targets_fn = patch(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            return_value=mock_targets,
        )
        mock_targets_fn.start()
        mock_manager = AsyncMock()
        mock_manager.notify.return_value = {"telegram": True}
        mock_manager_cls.return_value = mock_manager
        try:
            sent = await _send_instant_alerts(session, [self._job()])
        finally:
            mock_targets_fn.stop()

        assert sent == {"user-1": 1}
        mock_manager.notify.assert_called_once()
        call_args, call_kwargs = mock_manager.notify.call_args
        assert call_args[0] == ["telegram"]
        assert call_kwargs["recipient"] == {"telegram_chat_id": "123456"}
        assert call_kwargs["buttons"]

    @patch("interntrack.scheduler.jobs._job_match_score")
    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch(
        "interntrack.scheduler.jobs._latest_resume_skill_names",
        new_callable=AsyncMock,
    )
    async def test_skips_when_domain_does_not_match(
        self,
        mock_resume,
        mock_manager_cls,
        mock_match,
    ):
        from interntrack.scheduler.jobs import _send_instant_alerts

        mock_resume.return_value = {"python"}
        mock_match.return_value = 80.0
        session = AsyncMock()
        user = MagicMock()
        user.id = "user-1"
        user.telegram_chat_id = "123456"
        user.location = "Bangalore"
        mock_targets = [
            {
                "user_id": "user-1",
                "user": user,
                "prefs": {
                    "instant_alerts": True,
                    "domains": ["coding"],
                    "min_match_score": None,
                },
            },
        ]
        mock_targets_fn = patch(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            return_value=mock_targets,
        )
        mock_targets_fn.start()
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        try:
            sent = await _send_instant_alerts(
                session,
                [self._job(title="SOC Analyst", tags=["security"])],
            )
        finally:
            mock_targets_fn.stop()

        assert sent == {}
        mock_manager.notify.assert_not_called()

    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch(
        "interntrack.scheduler.jobs._latest_resume_skill_names",
        new_callable=AsyncMock,
    )
    async def test_skips_user_without_chat_id(
        self,
        mock_resume,
        mock_manager_cls,
    ):
        from interntrack.scheduler.jobs import _send_instant_alerts

        mock_resume.return_value = {"python"}

        session = AsyncMock()
        user = MagicMock()
        user.id = "user-1"
        user.telegram_chat_id = None
        user.location = "Bangalore"
        mock_targets = [
            {
                "user_id": "user-1",
                "user": user,
                "prefs": {
                    "instant_alerts": True,
                    "domains": [],
                    "min_match_score": None,
                },
            },
        ]
        mock_targets_fn = patch(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            return_value=mock_targets,
        )
        mock_targets_fn.start()
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        try:
            sent = await _send_instant_alerts(session, [self._job()])
        finally:
            mock_targets_fn.stop()

        assert sent == {}
        mock_manager.notify.assert_not_called()

    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch(
        "interntrack.scheduler.jobs._latest_resume_skill_names",
        new_callable=AsyncMock,
    )
    async def test_no_jobs_returns_empty(
        self,
        mock_resume,
        mock_manager_cls,
    ):
        from interntrack.scheduler.jobs import _send_instant_alerts

        sent = await _send_instant_alerts(AsyncMock(), [])
        assert sent == {}
        mock_manager_cls.assert_not_called()

    @patch("interntrack.scheduler.jobs._job_match_score")
    @patch("interntrack.scheduler.jobs.NotificationManager")
    @patch(
        "interntrack.scheduler.jobs._latest_resume_skill_names",
        new_callable=AsyncMock,
    )
    async def test_respects_min_match_score(
        self,
        mock_resume,
        mock_manager_cls,
        mock_match,
    ):
        from interntrack.scheduler.jobs import _send_instant_alerts

        mock_resume.return_value = {"python"}
        mock_match.return_value = 50.0
        session = AsyncMock()
        user = MagicMock()
        user.id = "user-1"
        user.telegram_chat_id = "123456"
        user.location = "Bangalore"
        mock_targets = [
            {
                "user_id": "user-1",
                "user": user,
                "prefs": {
                    "instant_alerts": True,
                    "domains": [],
                    "min_match_score": 90,
                },
            },
        ]
        mock_targets_fn = patch(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            return_value=mock_targets,
        )
        mock_targets_fn.start()
        mock_manager = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        try:
            sent = await _send_instant_alerts(session, [self._job()])
        finally:
            mock_targets_fn.stop()

        assert sent == {}
        mock_manager.notify.assert_not_called()


class TestJobOfDay:
    """The '🔥 Job of the day' highlight selection and rendering."""

    def test_returns_highest_score_job(self):
        from interntrack.scheduler.jobs import _job_of_day

        sections = [
            ("coding", [(40.0, {"title": "A"}), (90.0, {"title": "B"})]),
            ("security", [(None, {"title": "C"})]),
        ]
        score, job = _job_of_day(sections)
        assert score == 90.0
        assert job["title"] == "B"

    def test_falls_back_to_first_job_when_no_scores(self):
        from interntrack.scheduler.jobs import _job_of_day

        sections = [("coding", [(None, {"title": "X"}), (None, {"title": "Y"})])]
        score, job = _job_of_day(sections)
        assert score is None
        assert job["title"] == "X"

    def test_none_for_empty_sections(self):
        from interntrack.scheduler.jobs import _job_of_day

        assert _job_of_day([]) is None

    @pytest.mark.asyncio
    async def test_message_includes_job_of_day(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "title": "SOC Analyst",
                    "company": "Cyber Corp",
                    "url": "https://x.com/job",
                    "domain": "security",
                }
            ],
            "closing_soon": [],
            "follow_up": [],
        }
        with patch(
            "interntrack.scheduler.jobs._score_and_group_jobs",
            new=AsyncMock(return_value=[("security", [(72.5, report["new_jobs"][0])])]),
        ):
            msg = await build_daily_report_message(report, AsyncMock())
        assert "🔥 [JOB OF THE DAY]" in msg
        assert "72% match" in msg
        assert "SOC Analyst" in msg
        assert "https://x.com/job" in msg

    @pytest.mark.asyncio
    async def test_html_includes_job_of_day_card(self):
        from interntrack.scheduler.jobs import build_daily_report_html

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "new_jobs": [
                {
                    "title": "Pen Tester",
                    "company": "Acme",
                    "url": "https://x.com/pen",
                    "domain": "security",
                }
            ],
            "closing_soon": [],
            "follow_up": [],
        }
        with (
            patch(
                "interntrack.scheduler.jobs._score_and_group_jobs",
                new=AsyncMock(
                    return_value=[("security", [(61.0, report["new_jobs"][0])])]
                ),
            ),
            patch(
                "interntrack.scheduler.jobs._watched_company_names",
                new=AsyncMock(return_value=[]),
            ),
        ):
            html = await build_daily_report_html(report, AsyncMock())
        assert "🔥 JOB OF THE DAY" in html
        assert "MATCH 61%" in html
        assert "Pen Tester" in html

    def test_prefers_local_job_when_user_has_location(self):
        from interntrack.scheduler.jobs import _job_of_day

        sections = [
            (
                "security",
                [
                    (50.0, {"title": "Mumbai SOC", "location": "Mumbai"}),
                    (90.0, {"title": "Bangalore VAPT", "location": "Bangalore"}),
                ],
            )
        ]
        score, job = _job_of_day(sections, user_location="Bangalore")
        assert job["title"] == "Bangalore VAPT"
        assert score == 90.0

    def test_falls_back_to_best_anywhere_when_no_local_match(self):
        from interntrack.scheduler.jobs import _job_of_day

        sections = [
            ("security", [(85.0, {"title": "Remote SOC", "location": "Remote"})])
        ]
        score, job = _job_of_day(sections, user_location="Bangalore")
        assert job["title"] == "Remote SOC"
        assert score == 85.0
