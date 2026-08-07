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
