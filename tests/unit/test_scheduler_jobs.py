"""Unit tests for scheduler/jobs.py."""

import asyncio
from datetime import datetime
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


class TestSourceLabel:
    """The source chip shows which board a job came from in the alerts."""

    def test_friendly_labels_for_known_sources(self):
        from interntrack.scheduler.jobs import _source_label

        assert "LinkedIn" in _source_label("linkedin")
        assert "Internshala" in _source_label("internshala_direct")
        assert "Naukri" in _source_label("naukri")
        assert "RSS" in _source_label("rss_feed")
        assert "Shared link" in _source_label("manual")
        assert "Search engine" in _source_label("search_engine")

    def test_normalizes_enum_strings(self):
        from interntrack.scheduler.jobs import _source_label

        assert "LinkedIn" in _source_label("JobSource.LINKEDIN")
        assert "Cutshort" in _source_label("JobSource.CUTSHORT")

    def test_empty_source_is_empty_label(self):
        from interntrack.scheduler.jobs import _source_label

        assert _source_label(None) == ""
        assert _source_label("") == ""

    def test_unknown_source_falls_back_to_title_case(self):
        from interntrack.scheduler.jobs import _source_label

        assert _source_label("mystery_board") == "Mystery Board"

    @pytest.mark.asyncio
    async def test_message_includes_source_chip(self):
        """The Telegram/text digest shows the source board per job."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "SOC Analyst",
                    "company": "SecureCo",
                    "url": "https://a/apply",
                    "source": "linkedin",
                    "age_days": 0,
                    "domain": "security",
                    "is_applied": False,
                }
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "🗂" in message
        assert "LinkedIn" in message

    def test_html_card_includes_source(self):
        """The email card shows which board the job came from."""
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            80.0,
            {
                "title": "SOC Analyst",
                "company": "SecureCo",
                "location": "Bengaluru",
                "source": "internshala_direct",
            },
            "#e5484d",
        )

        assert "Internshala" in card


class TestJobHtmlCard:
    """Tests for the email digest job card (_job_html_card)."""

    def test_card_includes_description_block(self):
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            78.0,
            {
                "title": "SOC Analyst",
                "company": "Zscaler",
                "location": "Bengaluru",
                "url": "https://zscaler.example/apply",
                "description": (
                    "Monitor SIEM alerts, triage security incidents and "
                    "escalate to the incident response team."
                ),
            },
            "#e5484d",
        )

        assert "Monitor SIEM alerts" in card
        assert "triage security incidents" in card
        assert "background:#f8fafc" in card  # description block styling

    def test_card_skips_description_when_absent(self):
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            None,
            {"title": "SOC Analyst", "company": "Zscaler", "location": "Remote"},
            "#e5484d",
        )

        assert "background:#f8fafc" not in card

    def test_card_escapes_description_html(self):
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            None,
            {
                "title": "Security Engineer",
                "company": "Acme",
                "location": "Remote",
                "description": "<script>alert('xss')</script>Oversee security",
            },
            "#e5484d",
        )

        assert "<script>" not in card
        assert "&lt;script&gt;" not in card  # tag stripped, not shown raw
        assert "alert(&#x27;xss&#x27;)" in card  # quotes escaped too
        assert "Oversee security" in card

    def test_card_shows_walk_in_hiring_signal(self):
        """Direct hiring signals (walk-in drive) surface as a badge."""
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            None,
            {
                "title": "Security Intern",
                "company": "Acme",
                "location": "Chennai",
                "description": (
                    "Walk-in interview on Friday. Send resume to "
                    "hr@acme.example and join immediately."
                ),
            },
            "#e5484d",
        )

        assert "Walk-in interview" in card

    def test_card_shows_campus_hiring_signal_from_title(self):
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            None,
            {
                "title": "Campus Hiring Drive 2026",
                "company": "Acme",
                "location": "Bengaluru",
            },
            "#e5484d",
        )

        assert "Campus hiring" in card

    def test_card_no_hiring_signal_without_keywords(self):
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            None,
            {
                "title": "SOC Analyst",
                "company": "SecureCo",
                "location": "Remote",
                "description": "Monitor SIEM alerts and respond to incidents.",
            },
            "#e5484d",
        )

        assert "Walk-in" not in card
        assert "Now hiring" not in card
        assert "Campus" not in card

    def test_card_warns_on_single_scam_flag(self):
        """One red-flag group passes but shows a ⚠️ review note."""
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            None,
            {
                "title": "Home Data Entry",
                "company": "Unknown",
                "location": "Remote",
                "description": "Send money as registration fee to secure your seat.",
            },
            "#e5484d",
        )

        assert "Review carefully" in card
        assert "money transfer" in card


class TestScamDetection:
    """Heuristic scam guard for fresher-targeted fake postings."""

    def test_scam_signals_money_transfer(self):
        from interntrack.scheduler.jobs import _scam_signals

        job = {
            "title": "Work from home job",
            "description": "Pay a registration fee of ₹500 to apply.",
        }
        assert "money transfer" in _scam_signals(job)

    def test_clean_job_has_no_signals(self):
        from interntrack.scheduler.jobs import _scam_signals

        job = {
            "title": "SOC Analyst",
            "company": "Zscaler",
            "description": "Monitor SIEM alerts and respond to incidents.",
        }
        assert _scam_signals(job) == []

    def test_two_groups_is_likely_scam(self):
        from interntrack.scheduler.jobs import _is_likely_scam

        job = {
            "title": "Guaranteed job offer",
            "description": "Guaranteed placement after a joining fee. Pay via UPI.",
        }
        assert _is_likely_scam(job)

    def test_digest_drops_likely_scams_keeps_clean(self, monkeypatch):
        """Postings with 2+ red-flag groups never reach the digest sections."""
        from interntrack.scheduler.jobs import _score_and_group_jobs

        async def _no_skills(session, user_id=None):
            return None

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _no_skills
        )
        report = {
            "new_jobs": [
                {
                    "title": "Legit SOC Analyst",
                    "company": "Zscaler",
                    "domain": "security",
                    "experience_level": "fresher",
                    "description": "Monitor SIEM alerts.",
                },
                {
                    "title": "Fake Guaranteed Job",
                    "company": "Unknown",
                    "domain": "security",
                    "experience_level": "fresher",
                    "description": (
                        "Guaranteed placement after registration fee. "
                        "Send money via UPI to confirm."
                    ),
                },
            ],
        }
        sections = asyncio.run(_score_and_group_jobs(report, _FakeSession()))
        titles = [job["title"] for _, items in sections for _, job in items]
        assert "Legit SOC Analyst" in titles
        assert "Fake Guaranteed Job" not in titles

    def test_digest_subject_personalized_daily(self):
        """Daily subject carries job count + domains + location."""
        from interntrack.scheduler.jobs import _digest_subject

        subject = _digest_subject(
            {"new_jobs": [{"title": "a"}, {"title": "b"}, {"title": "c"}]},
            ["security"],
            "Bangalore",
        )
        assert subject == "🎯 3 security jobs in Bangalore"

    def test_digest_subject_weekly(self):
        from interntrack.scheduler.jobs import _digest_subject

        subject = _digest_subject(
            {"new_jobs": [{"title": "a"}]},
            ["data", "coding"],
            "Chennai",
            weekly=True,
        )
        assert subject == "📅 1 jobs this week (data, coding)"

    def test_digest_subject_falls_back_without_domains_or_location(self):
        from interntrack.scheduler.jobs import _digest_subject

        subject = _digest_subject({"new_jobs": []}, None, "")
        assert "0 matching jobs" in subject
        assert "Bangalore" in subject  # DEFAULT_LOCATION fallback

    def test_digest_subject_widened_daily_gets_star(self):
        """Auto-widened digests (widen_note set) carry a 🌟 so members
        know the email is a broader sweep, not their usual city window."""
        from interntrack.scheduler.jobs import _digest_subject

        subject = _digest_subject(
            {"new_jobs": [{"title": "a"}], "widen_note": "location"},
            ["security"],
            "Chennai",
        )
        assert subject == "🌟 🎯 1 security jobs in Chennai"

    def test_digest_subject_widened_weekly_gets_star(self):
        from interntrack.scheduler.jobs import _digest_subject

        subject = _digest_subject(
            {"new_jobs": [{"title": "a"}], "widen_note": "window"},
            ["govt"],
            "Pune",
            weekly=True,
        )
        assert subject == "🌟 📅 1 jobs this week (govt)"

    def test_hiring_drives_collects_instant_apply_roles(self):
        """Walk-in / campus / off-campus / virtual drives are pulled out of
        the digest sections; plain postings stay behind."""
        from interntrack.scheduler.jobs import _hiring_drives

        sections = [
            (
                "security",
                [
                    (80.0, {"title": "Walk-in interview for SOC interns"}),
                    (75.0, {"title": "Off-campus drive — VAPT freshers"}),
                    (90.0, {"title": "Security Analyst"}),
                ],
            ),
            (
                "coding",
                [(70.0, {"title": "Campus hiring 2026 — SDE"})],
            ),
        ]
        drives = _hiring_drives(sections)
        assert len(drives) == 3
        labels = [label for label, _, _ in drives]
        assert any("Walk-in" in label for label in labels)
        assert any("Campus" in label for label in labels)
        # The plain posting is not a drive.
        assert all("Security Analyst" not in str(job) for _, _, job in drives)

    def test_hiring_drives_respects_cap(self):
        from interntrack.scheduler.jobs import _hiring_drives

        sections = [
            (
                "security",
                [(80.0, {"title": f"Walk-in drive {i}"}) for i in range(9)],
            )
        ]
        assert len(_hiring_drives(sections, cap=5)) == 5

    def test_job_lines_include_signal_and_scam_warning(self):
        """Telegram lines carry the hiring signal + scam review note."""
        from interntrack.scheduler.jobs import _job_lines

        lines = _job_lines(
            None,
            {
                "title": "Walk-in interview for interns",
                "company": "Acme",
                "location": "Chennai",
                "description": "Send resume today. Registration fee required.",
                "url": "https://acme.example/apply",
            },
        )
        joined = "\n".join(lines)
        assert "Walk-in interview" in joined
        assert "money transfer" in joined

    def test_snippet_strips_html_tags(self):
        """Raw markup from greenhouse/notion/RSS sources never leaks into
        the digest snippet."""
        from interntrack.scheduler.jobs import _job_desc_snippet

        raw = (
            "<p><strong>Headquarters:</strong> Bengaluru</p>"
            "<div>Monitor <b>SIEM</b> alerts</div>"
        )
        snippet = _job_desc_snippet({"description": raw})

        assert "<" not in snippet
        assert ">" not in snippet
        assert "Headquarters:" in snippet
        assert "SIEM" in snippet

    def test_card_full_description_expandable(self):
        """Long postings get an expandable "What they expect" block with the
        complete description — the user asked for the full role expectations
        in the mail, not just a snippet."""
        from interntrack.scheduler.jobs import _job_html_card

        long_desc = (
            "Monitor SIEM alerts, triage security incidents and escalate to "
            "the incident response team. " * 30
        )
        card = _job_html_card(
            78.0,
            {
                "title": "SOC Analyst",
                "company": "Zscaler",
                "location": "Bengaluru",
                "description": long_desc,
            },
            "#e5484d",
        )

        assert "What they expect" in card
        assert "<details" in card
        # The full text survives (first words of the 7th repetition).
        assert "Monitor SIEM alerts" in card

    def test_card_no_expandable_for_short_description(self):
        """Short postings keep the snippet only — no empty details block."""
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            78.0,
            {
                "title": "SOC Analyst",
                "company": "Zscaler",
                "location": "Bengaluru",
                "description": "Monitor SIEM alerts and triage incidents.",
            },
            "#e5484d",
        )

        assert "What they expect" not in card
        assert "<details" not in card

    def test_card_fresher_badge(self):
        """Fresher/entry roles show a 🎓 Fresher badge on the email card."""
        from interntrack.scheduler.jobs import _job_fresher_rank, _job_html_card

        card = _job_html_card(
            80.0,
            {
                "title": "SOC Analyst",
                "company": "SecureCo",
                "location": "Bengaluru",
                "experience_level": "fresher",
            },
            "#e5484d",
        )
        assert "🎓 Fresher" in card
        assert _job_fresher_rank({"experience_level": "intern"}) == 0
        assert _job_fresher_rank({"experience_level": "0-2 years"}) == 1

    def test_sections_sort_fresher_first_then_freshest(self, monkeypatch):
        """Within a section, fresher roles lead, then newer postings come
        before older ones at the same score."""
        from interntrack.scheduler.jobs import _score_and_group_jobs

        async def _no_skills(session, user_id=None):
            return None

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _no_skills
        )
        report = {
            "new_jobs": [
                {
                    "title": "Senior SOC Lead",
                    "company": "A",
                    "domain": "security",
                    "experience_level": "senior",
                    "age_days": 1,
                },
                {
                    "title": "Fresher SOC Analyst",
                    "company": "B",
                    "domain": "security",
                    "experience_level": "fresher",
                    "age_days": 5,
                },
                {
                    "title": "Entry Analyst",
                    "company": "C",
                    "domain": "security",
                    "experience_level": "entry",
                    "age_days": 0,
                },
            ],
        }
        sections = asyncio.run(_score_and_group_jobs(report, _FakeSession()))
        titles = [job["title"] for _, items in sections for _, job in items]
        assert titles[0] == "Entry Analyst"  # fresher, newest
        assert titles[1] == "Fresher SOC Analyst"  # fresher, older
        assert titles[2] == "Senior SOC Lead"  # non-fresher last

    def test_salary_floor_drops_below_floor_keeps_unknown(self, monkeypatch):
        """target_salary drops known-below-floor jobs; unknown-salary stays."""
        from interntrack.scheduler.jobs import _score_and_group_jobs

        async def _no_skills(session, user_id=None):
            return None

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _no_skills
        )
        report = {
            "target_salary": 800000,
            "new_jobs": [
                {
                    "title": "Well Paid Role",
                    "company": "A",
                    "domain": "security",
                    "salary_min": 1200000,
                    "salary_currency": "INR",
                },
                {
                    "title": "Underpaid Role",
                    "company": "B",
                    "domain": "security",
                    "salary_min": 500000,
                    "salary_currency": "INR",
                },
                {
                    "title": "No Salary Listed",
                    "company": "C",
                    "domain": "security",
                },
            ],
        }
        sections = asyncio.run(_score_and_group_jobs(report, _FakeSession()))
        titles = [job["title"] for _, items in sections for _, job in items]
        assert titles == ["Well Paid Role", "No Salary Listed"]
        assert "Underpaid Role" not in titles

    def test_salary_floor_not_set_keeps_all(self, monkeypatch):
        from interntrack.scheduler.jobs import _score_and_group_jobs

        async def _no_skills(session, user_id=None):
            return None

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _no_skills
        )
        report = {
            "new_jobs": [
                {
                    "title": "Low Pay",
                    "company": "A",
                    "domain": "security",
                    "salary_min": 100000,
                    "salary_currency": "INR",
                },
            ],
        }
        sections = asyncio.run(_score_and_group_jobs(report, _FakeSession()))
        titles = [job["title"] for _, items in sections for _, job in items]
        assert titles == ["Low Pay"]


class _FakeSession:
    """Minimal stand-in so _score_and_group_jobs never touches the DB."""

    async def execute(self, *a, **k):
        raise AssertionError("unexpected DB call")


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
    async def test_message_includes_description_snippet(self):
        """The plain-text digest shows what the role expects (description)."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security"],
                    "description": (
                        "Perform penetration testing and vulnerability "
                        "assessments across web applications and APIs."
                    ),
                }
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "📝" in message
        assert "Perform penetration testing" in message
        assert "vulnerability assessments" in message

    @pytest.mark.asyncio
    async def test_message_escapes_description_html(self):
        """Telegram sends with HTML parse mode: leftover tags are stripped
        and any remaining & is escaped, or the whole digest send can fail
        (can't parse entities)."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "tags": ["security"],
                    "description": (
                        "<script>alert('x')</script> & Oversee <b>security</b>"
                    ),
                }
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "<script>" not in message
        assert "&lt;script&gt;" not in message  # tag stripped, not shown raw
        assert "alert(&#x27;x&#x27;)" in message  # quotes escaped too
        assert "&amp;" in message  # stray & still escaped

    @pytest.mark.asyncio
    async def test_message_skips_description_when_absent(self):
        """Jobs without a description render no 📝 line (no empty noise)."""
        from interntrack.scheduler.jobs import build_daily_report_message

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "tags": ["security"],
                }
            ],
        }

        message = await build_daily_report_message(report, None)

        assert "📝" not in message

    def test_job_desc_snippet_truncates_long_descriptions(self):
        """Long multi-paragraph descriptions collapse to one clean snippet."""
        from interntrack.scheduler.jobs import _job_desc_snippet

        long = "\n\n".join(
            ["We are looking for an enthusiastic " + "engineer " * 40] * 3
        )
        snippet = _job_desc_snippet({"description": long})

        assert snippet.endswith("…")
        assert "\n" not in snippet
        assert len(snippet) <= 180

    def test_job_desc_snippet_short_passthrough(self):
        from interntrack.scheduler.jobs import _job_desc_snippet

        assert _job_desc_snippet({"description": "  Simple role. "}) == "Simple role."
        assert _job_desc_snippet({}) == ""

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
            subject="🎯 1 matching jobs in Bangalore",
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

    def test_open_pixel_embeds_signed_token(self):
        from interntrack.scheduler.jobs import _open_pixel_html
        from interntrack.utils.helpers import verify_open_token

        pixel = _open_pixel_html("https://api.example.com", "u-pix")
        assert pixel.startswith(
            "<img src='https://api.example.com/api/v1/email/open?u=u-pix&t="
        )
        token = pixel.split("&t=")[-1].split("'")[0]
        assert verify_open_token("u-pix", token)
        assert _open_pixel_html("", "u-pix") == ""
        assert _open_pixel_html("https://api.example.com", None) == ""

    @pytest.mark.asyncio
    async def test_html_embeds_open_pixel_when_api_base_set(self, monkeypatch):
        from types import SimpleNamespace

        from interntrack.scheduler.jobs import build_daily_report_html

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: SimpleNamespace(
                api_base_url="https://api.example.com",
                secret_key="test-secret",  # noqa: S106 (test fixture)
            ),
        )
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
            html = await build_daily_report_html(report, AsyncMock(), user_id="u-pix")
        assert "/api/v1/email/open?u=u-pix&t=" in html

    @pytest.mark.asyncio
    async def test_member_footer_shown_only_without_dashboard_link(self):
        from interntrack.scheduler.jobs import (
            _member_footer_html,
            build_daily_report_html,
        )

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
            member_html = await build_daily_report_html(
                report, AsyncMock(), show_dashboard_link=False
            )
            owner_html = await build_daily_report_html(
                report, AsyncMock(), show_dashboard_link=True
            )
        assert "ask your admin" in member_html
        assert "ask your admin" not in owner_html
        assert "8 AM, 1 PM & 7 PM IST" in _member_footer_html()

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


class TestClosingSoonSweep:
    """Tests for the closing-soon alert sweep."""

    @pytest.mark.asyncio
    async def test_sends_matching_closing_jobs_once(self, monkeypatch):
        """A matching expiring job alerts the user with an Apply button."""
        from types import SimpleNamespace

        from interntrack.scheduler.jobs import _send_closing_soon_sweep

        class FakeJob:
            id = "j1"
            title = "SOC Analyst"
            company = "CyberCorp"
            location = "Bengaluru"
            url = "https://apply/j1"
            expires_at = None
            tags = ["soc", "security"]

        target = {
            "user_id": "u1",
            "prefs": {"domains": ["security"], "channels": ["email"]},
            "user": SimpleNamespace(
                email="u@x.com",
                telegram_chat_id="7",
                phone_number=None,
                location="Bangalore",
            ),
        }
        manager = MagicMock()
        manager.get_configured_channels.return_value = ["email"]
        manager.notify = AsyncMock(return_value={"email": True})
        pref = SimpleNamespace(closing_soon_sent=None)
        pref_row = MagicMock()
        pref_row.scalar_one_or_none.return_value = pref

        session = AsyncMock()
        session.execute.return_value = pref_row
        session.commit = AsyncMock()

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            AsyncMock(return_value=[target]),
        )
        monkeypatch.setattr(
            "interntrack.repositories.job_repository.JobRepository",
            MagicMock(
                return_value=MagicMock(
                    get_closing_soon=AsyncMock(return_value=[FakeJob()])
                )
            ),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._record_alert_history", AsyncMock()
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs.NotificationManager",
            lambda *_a, **_k: manager,
        )

        sent = await _send_closing_soon_sweep(session)

        assert sent == {"u1": 1}
        manager.notify.assert_awaited_once()
        call = manager.notify.await_args
        assert call.kwargs["recipient"]["email"] == "u@x.com"
        # Email-only member gets the styled HTML card with an Apply button
        # (the ``buttons`` kwarg is Telegram-only).
        assert "SOC Analyst" in call.args[1]
        assert "Apply now" in call.args[1]
        # Dedup bookkeeping persisted.
        assert pref.closing_soon_sent == ["j1"]

    @pytest.mark.asyncio
    async def test_skips_already_alerted_jobs(self, monkeypatch):
        """A job already flagged in a previous sweep is not re-sent."""
        from types import SimpleNamespace

        from interntrack.scheduler.jobs import _send_closing_soon_sweep

        class FakeJob:
            id = "j1"
            title = "SOC Analyst"
            company = "CyberCorp"
            location = "Bengaluru"
            url = "https://apply/j1"
            expires_at = None
            tags = ["soc", "security"]

        target = {
            "user_id": "u1",
            "prefs": {"domains": ["security"], "channels": ["email"]},
            "user": SimpleNamespace(
                email="u@x.com",
                telegram_chat_id=None,
                phone_number=None,
                location="Bangalore",
            ),
        }
        manager = MagicMock()
        manager.notify = AsyncMock(return_value={"email": True})
        pref = SimpleNamespace(closing_soon_sent=["j1"])
        pref_row = MagicMock()
        pref_row.scalar_one_or_none.return_value = pref

        session = AsyncMock()
        session.execute.return_value = pref_row

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            AsyncMock(return_value=[target]),
        )
        monkeypatch.setattr(
            "interntrack.repositories.job_repository.JobRepository",
            MagicMock(
                return_value=MagicMock(
                    get_closing_soon=AsyncMock(return_value=[FakeJob()])
                )
            ),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs.NotificationManager",
            lambda *_a, **_k: manager,
        )

        sent = await _send_closing_soon_sweep(session)

        assert sent == {}
        manager.notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_domain_mismatch_skips_user(self, monkeypatch):
        """A closing job outside the user's domains is ignored."""
        from types import SimpleNamespace

        from interntrack.scheduler.jobs import _send_closing_soon_sweep

        class FakeJob:
            id = "j1"
            title = "React Developer"
            company = "WebCo"
            location = "Bangalore"
            url = "https://apply/j1"
            expires_at = None
            tags = ["react"]

        target = {
            "user_id": "u1",
            "prefs": {"domains": ["security"], "channels": ["email"]},
            "user": SimpleNamespace(
                email="u@x.com",
                telegram_chat_id=None,
                phone_number=None,
                location="Bangalore",
            ),
        }
        manager = MagicMock()
        manager.notify = AsyncMock(return_value={"email": True})
        pref_row = MagicMock()
        pref_row.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute.return_value = pref_row

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            AsyncMock(return_value=[target]),
        )
        monkeypatch.setattr(
            "interntrack.repositories.job_repository.JobRepository",
            MagicMock(
                return_value=MagicMock(
                    get_closing_soon=AsyncMock(return_value=[FakeJob()])
                )
            ),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs.NotificationManager",
            lambda *_a, **_k: manager,
        )

        sent = await _send_closing_soon_sweep(session)

        assert sent == {}
        manager.notify.assert_not_awaited()


class TestWeeklyDigest:
    """The scheduler's weekly digest: 7-day window + top-engaged + toggle."""

    @pytest.mark.asyncio
    async def test_generate_daily_report_weekly_passes_flag_and_skips_disabled(
        self,
        monkeypatch,
    ):
        """weekly=True sends via _send_alert_for(weekly=True), skipping
        accounts that turned weekly_enabled off."""
        from interntrack.scheduler.jobs import generate_daily_report

        session = AsyncMock()
        sent_calls: list = []

        async def _fake_send(*args, **kwargs):
            sent_calls.append((args, kwargs))

        monkeypatch.setattr(
            "interntrack.scheduler.jobs.get_db_session",
            lambda: AsyncMock(
                __aenter__=AsyncMock(return_value=session),
                __aexit__=AsyncMock(return_value=False),
            ),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._enabled_alert_targets",
            AsyncMock(
                return_value=[
                    {
                        "user_id": "u-on",
                        "prefs": {
                            "is_enabled": True,
                            "weekly_enabled": True,
                            "domains": ["security"],
                            "channels": ["email"],
                            "min_match_score": None,
                            "last_alert_at": None,
                        },
                        "user": None,
                    },
                    {
                        "user_id": "u-off",
                        "prefs": {
                            "is_enabled": True,
                            "weekly_enabled": False,
                            "domains": ["security"],
                            "channels": ["email"],
                            "min_match_score": None,
                            "last_alert_at": None,
                        },
                        "user": None,
                    },
                ]
            ),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._send_alert_for",
            _fake_send,
        )

        await generate_daily_report(weekly=True)

        # Only the user with weekly_enabled=True got a weekly send.
        assert [c[0][1] for c in sent_calls] == ["u-on"]
        assert sent_calls[0][1].get("weekly") is True  # weekly kwarg

    @pytest.mark.asyncio
    async def test_weekly_send_uses_7day_window_and_attaches_top_engaged(
        self,
        monkeypatch,
    ):
        """_send_alert_for(weekly=True) spans 7 days and attaches
        top_engaged before delivery."""
        from interntrack.scheduler.jobs import _send_alert_for

        session = AsyncMock()

        class _FakeReportService:
            def __init__(self, session):
                pass

            async def generate_daily_report(self, **kwargs):
                return {
                    "summary": {
                        "new_jobs": 1,
                        "new_applications": 0,
                        "total_applications": 0,
                    },
                    "new_jobs": [
                        {"title": "SOC Analyst", "company": "X", "url": "https://x"}
                    ],
                    "closing_soon": [],
                    "follow_up": [],
                }

        manager = MagicMock()
        manager.notify = AsyncMock(return_value={"email": True})

        deliver_kwargs: dict = {}

        async def _fake_deliver(*args, **kwargs):
            deliver_kwargs.update(kwargs)
            return {"email": True}

        monkeypatch.setattr(
            "interntrack.scheduler.jobs.ReportService",
            _FakeReportService,
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs.NotificationManager",
            lambda *_a, **_k: manager,
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._mark_alert_sent",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._record_alert_history",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._weekly_top_engaged",
            AsyncMock(return_value=[{"title": "Hot Job", "engagement_score": 5.0}]),
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._deliver_alert",
            _fake_deliver,
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names",
            AsyncMock(return_value=None),
        )

        await _send_alert_for(
            session,
            "u-on",
            {
                "domains": ["security"],
                "channels": ["email"],
                "min_match_score": None,
                "last_alert_at": None,
            },
            None,
            weekly=True,
        )

        assert deliver_kwargs.get("weekly") is True
        assert "jobs this week" in deliver_kwargs.get("subject", "")
        assert "security" in deliver_kwargs.get("subject", "")

    @pytest.mark.asyncio
    async def test_sent_urls_for_aggregates_user_history(self):
        """_sent_urls_for collects job URLs from a member's stored digest
        snapshots so the auto-widen fallback never re-sends what they
        already received. Other users' histories are ignored."""
        from interntrack.scheduler.jobs import _sent_urls_for

        class _Job:
            def __init__(self, url):
                self.url = url

        class _Row:
            def __init__(self, user_id, jobs):
                self.user_id = user_id
                self.jobs = jobs

        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(
                        all=lambda: [
                            _Row("u1", [{"url": "https://a"}, {"url": ""}]),
                            _Row("u1", [{"url": "https://b"}]),
                            _Row("u2", [{"url": "https://other"}]),
                            _Row("u1", None),
                        ]
                    )
                )
            )
        )

        urls = await _sent_urls_for(session, "u1")
        assert urls == {"https://a", "https://b"}

        # Never raises on a broken session.
        session.execute = AsyncMock(side_effect=RuntimeError("db down"))
        assert await _sent_urls_for(session, "u1") == set()

    @pytest.mark.asyncio
    async def test_widened_report_falls_back_to_all_india(self):
        """When the city window yields nothing (or only already-sent URLs),
        the fallback retries a wider window and then all-India, filtering
        out every URL the member already received."""
        from interntrack.scheduler.jobs import _widened_report

        calls: list[dict] = []

        class _FakeService:
            async def generate_daily_report(self, **kwargs):
                calls.append(kwargs)
                location = kwargs.get("location")
                if location == "Chennai":
                    # Only an already-seen URL in the city window.
                    return {"new_jobs": [{"title": "Old", "url": "https://seen"}]}
                # All-India: fresh job.
                return {"new_jobs": [{"title": "Remote SOC", "url": "https://fresh"}]}

        report = await _widened_report(
            _FakeService(),
            domains=["security"],
            prefs={"min_match_score": None},
            user_location="Chennai",
            include_remote=True,
            seen_urls={"https://seen"},
        )

        assert report is not None
        assert [j["url"] for j in report["new_jobs"]] == ["https://fresh"]
        assert report["widen_note"] == "location"
        assert calls[0]["location"] == "Chennai"  # city first
        assert calls[1]["location"] is None  # then all-India

    @pytest.mark.asyncio
    async def test_widened_report_returns_none_when_nothing_matches(self):
        from interntrack.scheduler.jobs import _widened_report

        class _Empty:
            async def generate_daily_report(self, **kwargs):
                return {"new_jobs": []}

        report = await _widened_report(
            _Empty(),
            domains=["security"],
            prefs={},
            user_location="Chennai",
            include_remote=False,
            seen_urls=set(),
        )
        assert report is None

        # Never raises on a broken service.
        class _Broken:
            async def generate_daily_report(self, **kwargs):
                raise RuntimeError("boom")

        assert (
            await _widened_report(
                _Broken(),
                domains=["security"],
                prefs={},
                user_location=None,
                include_remote=False,
                seen_urls=set(),
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_weekly_top_engaged_formula(
        self,
        monkeypatch,
    ):
        """Engagement = 3*apps + 2*bookmarks + 0.5*views, sorted desc."""
        from interntrack.scheduler.jobs import _weekly_top_engaged

        session = AsyncMock()

        class _Job:
            def __init__(self, jid, views, created):
                self.id = jid
                self.title = f"Job {jid}"
                self.company = "Co"
                self.location = "BLR"
                self.url = "https://x"
                self.view_count = views
                self.is_active = True
                self.created_at = created

        jobs = [_Job("a", 10, 1), _Job("b", 0, 1)]
        app_rows = [("a", 2)]  # job a: 2 applications
        bm_rows = [("a", 1)]  # job a: 1 bookmark

        async def _fake_execute(stmt):
            s = str(stmt).lower()

            class _R:
                def scalars(self):
                    return self

                def all(self):
                    return jobs

            class _R2:
                def __init__(self, rows):
                    self.rows = rows

                def all(self):
                    return self.rows

            if "bookmark" in s:
                return _R2(bm_rows)
            if "application" in s:
                return _R2(app_rows)
            return _R()

        session.execute = _fake_execute
        monkeypatch.setattr(
            "interntrack.utils.helpers.utcnow",
            lambda: datetime(2026, 8, 10),
        )

        top = await _weekly_top_engaged(session)

        # a: 2*3 + 1*2 + 10*0.5 = 13.0 ; b: 0 -> excluded.
        assert len(top) == 1
        assert top[0]["id"] == "a"
        assert top[0]["engagement_score"] == 13.0


class TestDigestFooter:
    """Email / Telegram footer links to the public dashboard."""

    def test_footer_html_renders_links_when_dashboard_url_set(
        self,
        monkeypatch,
    ):
        from interntrack.scheduler.jobs import _digest_footer_html

        class _Settings:
            dashboard_url = "https://dash.example.com"

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        html = _digest_footer_html()
        assert "Open full dashboard" in html
        assert "Settings page" in html
        assert "https://dash.example.com" in html

    def test_footer_html_empty_when_no_url(self, monkeypatch):
        from interntrack.scheduler.jobs import _digest_footer_html

        class _Settings:
            dashboard_url = None

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        assert _digest_footer_html() == ""

    def test_footer_text_renders_when_dashboard_url_set(self, monkeypatch):
        from interntrack.scheduler.jobs import _digest_footer_text

        class _Settings:
            dashboard_url = "https://dash.example.com"

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        txt = _digest_footer_text()
        assert "Open full dashboard" in txt
        assert "https://dash.example.com" in txt

    def test_footer_text_empty_when_no_url(self, monkeypatch):
        from interntrack.scheduler.jobs import _digest_footer_text

        class _Settings:
            dashboard_url = ""

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        assert _digest_footer_text() == ""

    @pytest.mark.asyncio
    async def test_html_omits_dashboard_link_for_member(self, monkeypatch):
        """Members get the digest without the dashboard/manage footer."""
        from interntrack.scheduler.jobs import build_daily_report_html

        class _Settings:
            dashboard_url = "https://dash.example.com"

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        report = {"summary": {"new_jobs": 0}, "new_jobs": []}
        with (
            patch(
                "interntrack.scheduler.jobs._score_and_group_jobs",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "interntrack.scheduler.jobs._watched_company_names",
                new=AsyncMock(return_value=[]),
            ),
        ):
            html = await build_daily_report_html(
                report, AsyncMock(), show_dashboard_link=False
            )
        assert "Open full dashboard" not in html
        assert "Settings page" not in html

    @pytest.mark.asyncio
    async def test_html_keeps_dashboard_link_for_owner(self, monkeypatch):
        """The owner's own digest still links to the dashboard."""
        from interntrack.scheduler.jobs import build_daily_report_html

        class _Settings:
            dashboard_url = "https://dash.example.com"

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        report = {"summary": {"new_jobs": 0}, "new_jobs": []}
        with (
            patch(
                "interntrack.scheduler.jobs._score_and_group_jobs",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "interntrack.scheduler.jobs._watched_company_names",
                new=AsyncMock(return_value=[]),
            ),
        ):
            html = await build_daily_report_html(
                report, AsyncMock(), show_dashboard_link=True
            )
        assert "Open full dashboard" in html

    @pytest.mark.asyncio
    async def test_chunks_omit_dashboard_link_for_member(self, monkeypatch):
        """Telegram chunks for a member drop the dashboard footer too."""
        from interntrack.scheduler.jobs import build_alert_chunks

        class _Settings:
            dashboard_url = "https://dash.example.com"

        monkeypatch.setattr(
            "interntrack.config.get_settings",
            lambda: _Settings(),
        )
        report = {"summary": {"new_jobs": 0}, "new_jobs": []}
        with (
            patch(
                "interntrack.scheduler.jobs._score_and_group_jobs",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "interntrack.scheduler.jobs._watched_company_names",
                new=AsyncMock(return_value=[]),
            ),
        ):
            chunks = await build_alert_chunks(
                report, AsyncMock(), show_dashboard_link=False
            )
        joined = "\n".join(text for text, _ in chunks)
        assert "Open full dashboard" not in joined


class TestJobSkillsLine:
    """Digests surface the skills each role expects ("what they expect")."""

    def test_skills_txt_empty(self):
        from interntrack.scheduler.jobs import _skills_txt

        assert _skills_txt({}) == ""
        assert _skills_txt({"required_skills": [], "tags": []}) == ""
        assert _skills_txt({"tags": [None, "", "  "]}) == ""

    def test_skills_txt_prefers_required_skills_and_dedupes(self):
        from interntrack.scheduler.jobs import _skills_txt

        job = {
            "required_skills": ["Splunk", "Splunk", "SIEM", "  ", "Incident Response"],
            "tags": ["python", "soc"],
        }
        # required_skills first, tags top up to the cap.
        assert _skills_txt(job) == "Splunk, SIEM, Incident Response, python, soc"

    def test_skills_txt_falls_back_to_tags_and_caps(self):
        from interntrack.scheduler.jobs import _skills_txt

        job = {"tags": ["a", "b", "c", "d", "e", "f", "g", "h"]}
        assert _skills_txt(job, limit=4) == "a, b, c, d"
        assert len(_skills_txt(job).split(", ")) == 6

    def test_job_lines_include_skills(self):
        from interntrack.scheduler.jobs import _job_lines

        job = {
            "title": "SOC Analyst",
            "company": "ACME",
            "url": "https://example.com/job/1",
            "required_skills": ["Splunk", "SIEM"],
            "age_days": 1,
        }
        lines = _job_lines(82, job)
        assert any("🛠 Skills: Splunk, SIEM" in line for line in lines)

    def test_job_html_card_include_skills(self):
        from interntrack.scheduler.jobs import _job_html_card

        job = {
            "title": "SOC Analyst",
            "company": "ACME",
            "url": "https://example.com/job/1",
            "required_skills": ["Splunk", "SIEM"],
            "age_days": 1,
        }
        html = _job_html_card(82, job, "#2563eb")
        assert "🛠 Skills: Splunk, SIEM" in html

    def test_job_html_card_omits_skills_when_none(self):
        from interntrack.scheduler.jobs import _job_html_card

        job = {"title": "Job", "url": "https://example.com/job/1", "age_days": 1}
        html = _job_html_card(82, job, "#2563eb")
        assert "🛠 Skills:" not in html

    def test_skills_txt_filters_non_skill_noise(self):
        from interntrack.scheduler.jobs import _skills_txt

        job = {"tags": ["Bengaluru", "Full-time", "Hybrid", "Python", "Splunk"]}
        assert _skills_txt(job) == "Python, Splunk"

    def test_skills_txt_empty_required_skills_does_not_suppress_tags(self):
        from interntrack.scheduler.jobs import _skills_txt

        job = {"required_skills": ["", None], "tags": ["Splunk", "SIEM"]}
        assert _skills_txt(job) == "Splunk, SIEM"

    def test_skills_line_escapes_special_chars(self):
        from interntrack.scheduler.jobs import _job_html_card, _job_lines

        job = {
            "title": "Dev",
            "url": "https://example.com/job/1",
            "age_days": 1,
            "required_skills": ["C++", "R&D"],
        }
        lines = _job_lines(82, job)
        assert any("🛠 Skills: C++, R&amp;D" in line for line in lines)
        html = _job_html_card(82, job, "#2563eb")
        assert "🛠 Skills: C++, R&amp;D" in html
        assert "<script>" not in html


class TestWeeklySkillGap:
    """The weekly digest's 'skills to learn next' block."""

    def test_skill_gap_counts_empty_without_resume(self):
        from interntrack.scheduler.jobs import _skill_gap_counts

        assert _skill_gap_counts(None, [{}]) == []
        assert _skill_gap_counts(set(), [{}]) == []

    def test_skill_gap_counts_ranks_and_caps(self):
        from interntrack.scheduler.jobs import _skill_gap_counts

        jobs = [
            {"required_skills": ["Splunk", "SIEM", "Linux"]},
            {"required_skills": ["Splunk", "SIEM"]},
            {"required_skills": ["Splunk", "AWS"]},
        ]
        gap = _skill_gap_counts({"python"}, jobs, limit=2)
        assert gap == [
            {"skill": "Splunk", "count": 3},
            {"skill": "SIEM", "count": 2},
        ]

    def test_skill_gap_counts_matches_resume_and_filters_noise(self):
        from interntrack.scheduler.jobs import _skill_gap_counts

        jobs = [
            {"required_skills": ["Splunk", "python", "Bengaluru", "Full-time"]},
            {"required_skills": ["splunk", "SIEM"]},
        ]
        gap = _skill_gap_counts({"python"}, jobs)
        # python already on the resume; Splunk counted once per job; noise dropped.
        assert gap == [
            {"skill": "Splunk", "count": 2},
            {"skill": "SIEM", "count": 1},
        ]

    def _report(self, jobs):
        return {
            "summary": {
                "new_jobs": len(jobs),
                "new_applications": 0,
                "total_applications": 0,
            },
            "new_jobs": jobs,
        }

    def _soc_jobs(self):
        return [
            {
                "id": "job-1",
                "title": "SOC Analyst",
                "company": "Acme Corp",
                "url": "https://acme.example/apply",
                "location": "Bengaluru",
                "required_skills": ["Splunk", "SIEM", "Python"],
                "tags": ["soc"],
                "age_days": 1,
            },
            {
                "id": "job-2",
                "title": "Security Engineer",
                "company": "Beta Inc",
                "url": "https://beta.example/apply",
                "location": "Bengaluru",
                "required_skills": ["Splunk", "AWS"],
                "tags": ["security"],
                "age_days": 2,
            },
        ]

    class FakeResume:
        skills = [{"name": "Python", "category": "scripting"}]

    class FakeResult:
        def scalar_one_or_none(self):
            return TestWeeklySkillGap.FakeResume()

    class FakeSession:
        async def execute(self, *args, **kwargs):
            return TestWeeklySkillGap.FakeResult()

    @pytest.mark.asyncio
    async def test_weekly_message_lists_gap_but_daily_does_not(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = self._report(self._soc_jobs())
        weekly = await build_daily_report_message(
            report, self.FakeSession(), weekly=True
        )
        assert "🛠 Skills to learn next" in weekly
        assert "Splunk — wanted by 2 job(s)" in weekly
        assert "SIEM — wanted by 1 job(s)" in weekly

        daily = await build_daily_report_message(
            report, self.FakeSession(), weekly=False
        )
        assert "Skills to learn next" not in daily

    @pytest.mark.asyncio
    async def test_weekly_html_card_lists_gap_but_daily_does_not(self):
        from interntrack.scheduler.jobs import build_daily_report_html

        report = self._report(self._soc_jobs())
        weekly = await build_daily_report_html(report, self.FakeSession(), weekly=True)
        assert "🛠 Skills to learn next" in weekly
        assert "Splunk" in weekly
        assert "wanted" not in weekly  # email uses chips, not the text wording

        daily = await build_daily_report_html(report, self.FakeSession(), weekly=False)
        assert "Skills to learn next" not in daily

    @pytest.mark.asyncio
    async def test_weekly_telegram_chunks_include_gap(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        report = self._report(self._soc_jobs())
        chunks = await build_alert_chunks(
            report, self.FakeSession(), weekly=True, user_id="u1"
        )
        texts = [text for text, _buttons in chunks]
        assert any("Skills to learn next" in t for t in texts)
        assert any("Splunk — wanted by 2 job(s)" in t for t in texts)

        daily_chunks = await build_alert_chunks(
            report, self.FakeSession(), weekly=False, user_id="u1"
        )
        daily_texts = [text for text, _buttons in daily_chunks]
        assert not any("Skills to learn next" in t for t in daily_texts)


class TestSkillLearnLinks:
    """Curated + fallback learning links on the weekly skills-gap block."""

    def test_skill_learn_url_curated(self):
        from interntrack.scheduler.jobs import _skill_learn_url

        assert _skill_learn_url("Splunk") == (
            "https://www.splunk.com/en_us/training/free-courses/overview.html"
        )
        assert _skill_learn_url("Python") == ("https://docs.python.org/3/tutorial/")

    def test_skill_learn_url_falls_back_to_youtube(self):
        from interntrack.scheduler.jobs import _skill_learn_url

        url = _skill_learn_url("Zero Trust")
        assert url is not None
        assert url.startswith("https://www.youtube.com/results?search_query=")
        assert "course" in url

    def test_skill_learn_url_empty(self):
        from interntrack.scheduler.jobs import _skill_learn_url

        assert _skill_learn_url("") is None
        assert _skill_learn_url(None) is None

    @pytest.mark.asyncio
    async def test_weekly_message_includes_learn_links(self):
        from interntrack.scheduler.jobs import build_daily_report_message

        report = TestWeeklySkillGap()._report(TestWeeklySkillGap()._soc_jobs())
        weekly = await build_daily_report_message(
            report, TestWeeklySkillGap.FakeSession(), weekly=True
        )
        assert "📚 Learn Splunk: https://www.splunk.com" in weekly

    @pytest.mark.asyncio
    async def test_weekly_chunks_add_learn_buttons(self):
        from interntrack.scheduler.jobs import build_alert_chunks

        report = TestWeeklySkillGap()._report(TestWeeklySkillGap()._soc_jobs())
        chunks = await build_alert_chunks(
            report, TestWeeklySkillGap.FakeSession(), weekly=True, user_id="u1"
        )
        buttons = [
            (label, url) for _text, btn_list in chunks for label, url in btn_list
        ]
        assert any(label == "📚 Learn Splunk" for label, _url in buttons)
        assert any(
            url == "https://www.splunk.com/en_us/training/free-courses/overview.html"
            for _label, url in buttons
        )

    @pytest.mark.asyncio
    async def test_weekly_html_links_chips_to_resources(self):
        from interntrack.scheduler.jobs import build_daily_report_html

        report = TestWeeklySkillGap()._report(TestWeeklySkillGap()._soc_jobs())
        weekly = await build_daily_report_html(
            report, TestWeeklySkillGap.FakeSession(), weekly=True
        )
        assert "splunk.com/en_us/training" in weekly
        assert "target='_blank'" in weekly


class TestWeeklySalaryInsight:
    """Median-pay insight on the weekly digest."""

    @pytest.mark.asyncio
    async def test_weekly_salary_insight_formats_inr(self, monkeypatch):
        from interntrack.scheduler.jobs import _weekly_salary_insight

        async def _fake_benchmark(session, domain, city):
            assert domain == "security"
            assert city == "Bangalore"
            return {
                "domain": "security",
                "city": "Bangalore",
                "count": 12,
                "median": 800_000,
                "currency": "INR",
            }

        monkeypatch.setattr(
            "interntrack.api.v1.salary_insights.salary_benchmark_for",
            _fake_benchmark,
        )
        line = await _weekly_salary_insight(
            AsyncMock(), ["security"], "Bangalore, India"
        )
        assert line == (
            "💰 Median security pay in Bangalore: ₹6.0L–₹10.0L (from 12 live postings)"
        )

    @pytest.mark.asyncio
    async def test_weekly_salary_insight_none_without_data(self, monkeypatch):
        from interntrack.scheduler.jobs import _weekly_salary_insight

        async def _none(session, domain, city):
            return None

        monkeypatch.setattr(
            "interntrack.api.v1.salary_insights.salary_benchmark_for", _none
        )
        assert (
            await _weekly_salary_insight(AsyncMock(), ["security"], "Bangalore") is None
        )

    @pytest.mark.asyncio
    async def test_weekly_builders_include_salary_line(self, monkeypatch):
        from interntrack.scheduler.jobs import (
            build_alert_chunks,
            build_daily_report_html,
            build_daily_report_message,
        )

        async def _fake_benchmark(session, domain, city):
            return {
                "domain": "security",
                "city": "Bangalore",
                "count": 12,
                "median": 800_000,
                "currency": "INR",
            }

        monkeypatch.setattr(
            "interntrack.api.v1.salary_insights.salary_benchmark_for",
            _fake_benchmark,
        )
        jobs = TestWeeklySkillGap()._soc_jobs()
        for j in jobs:
            j["domain"] = "security"
        report = TestWeeklySkillGap()._report(jobs)
        session = TestWeeklySkillGap.FakeSession()
        msg = await build_daily_report_message(
            report,
            session,
            weekly=True,
            domains=["security"],
            user_location="Bangalore",
        )
        assert "💰 Median security pay in Bangalore" in msg
        html = await build_daily_report_html(
            report,
            session,
            weekly=True,
            domains=["security"],
            user_location="Bangalore",
        )
        assert "Median security pay in Bangalore" in html
        chunks = await build_alert_chunks(
            report,
            session,
            weekly=True,
            domains=["security"],
            user_location="Bangalore",
            user_id="u1",
        )
        texts = [text for text, _buttons in chunks]
        assert any("Median security pay in Bangalore" in t for t in texts)

    @pytest.mark.asyncio
    async def test_weekly_salary_insight_formats_usd(self, monkeypatch):
        from interntrack.scheduler.jobs import _weekly_salary_insight

        async def _fake_benchmark(session, domain, city):
            return {
                "domain": "security",
                "city": "Remote",
                "count": 4,
                "median": 90_000,
                "currency": "USD",
            }

        monkeypatch.setattr(
            "interntrack.api.v1.salary_insights.salary_benchmark_for",
            _fake_benchmark,
        )
        line = await _weekly_salary_insight(AsyncMock(), ["security"], "")
        assert line == (
            "💰 Median security pay in Remote: $67k–$112k (from 4 live postings)"
        )

    @pytest.mark.asyncio
    async def test_weekly_salary_insight_prefers_security_domain(self, monkeypatch):
        from interntrack.scheduler.jobs import _weekly_salary_insight

        seen: list[str] = []

        async def _fake_benchmark(session, domain, city):
            seen.append(domain)
            return {
                "domain": domain,
                "city": "Remote",
                "count": 1,
                "median": 800_000,
                "currency": "INR",
            }

        monkeypatch.setattr(
            "interntrack.api.v1.salary_insights.salary_benchmark_for",
            _fake_benchmark,
        )
        await _weekly_salary_insight(AsyncMock(), ["coding", "security"], "Bangalore")
        # security is tried first even when it is second in the pref list.
        assert seen[0] == "security"


class TestDigestMarketSections:
    """Tests for the 🏢 Top companies and 🎓 Internships & fresher sections."""

    @pytest.mark.asyncio
    async def test_html_shows_top_companies_near(self, monkeypatch):
        """Daily HTML email renders the market snapshot when companies exist."""
        from interntrack.scheduler.jobs import build_daily_report_html

        async def _fake_companies(session, user_location=None, include_remote=True):
            return [("Acme Corp", 4, "₹12–15 LPA"), ("SecureCo", 2, "")]

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._top_companies_near", _fake_companies
        )
        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "location": "Bengaluru",
                    "url": "https://acme.example/apply",
                    "tags": ["security"],
                    "experience_level": "senior",
                }
            ],
        }
        html = await build_daily_report_html(
            report, AsyncMock(), user_location="Bangalore"
        )
        assert "Top companies hiring near you" in html
        assert "Acme Corp" in html
        assert "4" in html

    @pytest.mark.asyncio
    async def test_html_fresher_highlight_for_fresher_only(self, monkeypatch):
        """Fresher-only users get the 🎓 section with their fresher roles."""
        from interntrack.scheduler.jobs import build_daily_report_html

        async def _fake_fresher(report, session, domains=None, user_id=None, limit=3):
            return [
                {
                    "title": "SOC Intern",
                    "company": "SecureCo",
                    "location": "Pune",
                    "url": "https://secure.example/intern",
                    "experience_level": "intern",
                    "tags": ["security"],
                }
            ]

        async def _fake_companies(session, user_location=None, include_remote=True):
            return []

        monkeypatch.setattr("interntrack.scheduler.jobs._fresher_roles", _fake_fresher)
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._top_companies_near", _fake_companies
        )
        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "fresher_only": True,
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "SOC Intern",
                    "company": "SecureCo",
                    "location": "Pune",
                    "url": "https://secure.example/intern",
                    "tags": ["security"],
                    "experience_level": "intern",
                }
            ],
        }
        html = await build_daily_report_html(report, AsyncMock())
        assert (
            "🎓 Internships &amp; fresher roles" in html
            or "🎓 Internships & fresher roles" in html
        )
        assert "SOC Intern" in html

    @pytest.mark.asyncio
    async def test_no_fresher_section_when_not_fresher_only(self, monkeypatch):
        """Non-fresher-only users never see the 🎓 highlight."""
        from interntrack.scheduler.jobs import build_daily_report_html

        async def _fake_companies(session, user_location=None, include_remote=True):
            return []

        async def _unexpected(report, session, domains=None, user_id=None, limit=3):
            raise AssertionError("_fresher_roles must not be called")

        monkeypatch.setattr("interntrack.scheduler.jobs._fresher_roles", _unexpected)
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._top_companies_near", _fake_companies
        )
        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security"],
                }
            ],
        }
        html = await build_daily_report_html(report, AsyncMock())
        assert "Internships &amp; fresher" not in html

    @pytest.mark.asyncio
    async def test_message_shows_top_companies_and_fresher(self, monkeypatch):
        """Plain-text digest renders both new sections."""
        from interntrack.scheduler.jobs import build_daily_report_message

        async def _fake_companies(session, user_location=None, include_remote=True):
            return [("Acme Corp", 4, "₹8 LPA")]

        async def _fake_fresher(report, session, domains=None, user_id=None, limit=3):
            return [
                {
                    "title": "SOC Intern",
                    "company": "SecureCo",
                    "location": "Pune",
                    "url": "https://secure.example/intern",
                    "experience_level": "intern",
                    "tags": ["security"],
                }
            ]

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._top_companies_near", _fake_companies
        )
        monkeypatch.setattr("interntrack.scheduler.jobs._fresher_roles", _fake_fresher)
        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "fresher_only": True,
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "SOC Intern",
                    "company": "SecureCo",
                    "location": "Pune",
                    "url": "https://secure.example/intern",
                    "tags": ["security"],
                    "experience_level": "intern",
                }
            ],
        }
        message = await build_daily_report_message(
            report, AsyncMock(), user_location="Pune"
        )
        assert "Top companies hiring near Pune" in message
        assert "Acme Corp — 4 fresh role(s) · ₹8 LPA" in message
        assert "🎓 Internships & fresher roles:" in message
        assert "SOC Intern" in message

    @pytest.mark.asyncio
    async def test_html_company_chip_shows_salary(self, monkeypatch):
        """Company chips render the median salary band when available."""
        from interntrack.scheduler.jobs import build_daily_report_html

        async def _fake_companies(session, user_location=None, include_remote=True):
            return [("Acme Corp", 4, "₹12–15 LPA")]

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._top_companies_near", _fake_companies
        )
        report = {
            "summary": {"new_jobs": 1, "new_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security"],
                }
            ],
        }
        html = await build_daily_report_html(report, AsyncMock())
        assert "₹12–15 LPA" in html
        assert "💰" in html

    def test_salary_band_txt(self):
        """salary_band_txt renders INR lakhs, thousands and empty bands."""
        from interntrack.utils.helpers import salary_band_txt

        assert salary_band_txt(800000, 1200000) == "₹8 LPA–₹12 LPA"
        assert salary_band_txt(45000, 60000) == "₹45K–₹60K"
        assert salary_band_txt(1200000, None) == "₹12 LPA"
        assert salary_band_txt(None, None) == ""
        assert salary_band_txt(80000, 100000, currency="USD") == "$80k–$100k"


class TestRequirementsChecklist:
    """Tests for the ✅/⬜ requirements checklist on job cards."""

    def test_html_checklist_renders_matched_and_missing(self):
        """With resume skills, cards render ✅ matched / ⬜ missing chips."""
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            60.0,
            {
                "title": "SOC Analyst",
                "company": "SecureCo",
                "tags": ["splunk", "python", "siem"],
            },
            "#e5484d",
            resume_skills={"python"},
        )
        assert "REQUIREMENTS CHECKLIST" in card
        assert "✅ python" in card
        assert "⬜ splunk" in card
        # Missing skills carry a 📚 learn link so the member can close the gap.
        assert "📚 learn" in card
        assert "youtube.com" in card or "course" in card

    def test_html_checklist_skipped_without_resume(self):
        """No resume skills → no checklist block on the card."""
        from interntrack.scheduler.jobs import _job_html_card

        card = _job_html_card(
            80.0,
            {
                "title": "SOC Analyst",
                "company": "SecureCo",
                "tags": ["splunk"],
            },
            "#e5484d",
        )
        assert "REQUIREMENTS CHECKLIST" not in card

    def test_lines_checklist_plain_text(self):
        """Plain-text digest shows compact ✅/⬜ skill chips."""
        from interntrack.scheduler.jobs import _skills_checklist_lines

        rows = _skills_checklist_lines(
            {"tags": ["splunk", "python", "siem"]},
            {"python"},
        )
        assert any("✅python" in r for r in rows)
        assert any("⬜splunk" in r for r in rows)

    def test_lines_checklist_skipped_without_resume(self):
        """No resume → empty checklist (never raises)."""
        from interntrack.scheduler.jobs import _skills_checklist_lines

        assert _skills_checklist_lines({"tags": ["splunk"]}, None) == []
        assert _skills_checklist_lines({"tags": []}, {"python"}) == []


class _FakeOwnerUser:
    """Minimal User stand-in for owner-failure-alert tests."""

    def __init__(self, email="owner@example.com", chat="12345"):
        self.email = email
        self.telegram_chat_id = chat
        self.name = "Owner"
        self.created_at = None


class TestOwnerFailureAlert:
    """Tests for the ⚠️ owner Telegram ping on member email failures."""

    @pytest.mark.asyncio
    async def test_pings_owner_when_email_fails(self, monkeypatch):
        """A failed member email triggers a Telegram ping to the owner."""
        from interntrack.scheduler.jobs import _notify_owner_of_failure

        class _Settings:
            telegram_bot_token = "bot:token"
            telegram_chat_id = "111"
            team_owner_email = None
            is_telegram_configured = True

        class _Result:
            def scalars(self):
                return self

            def all(self):
                return [_FakeOwnerUser()]

        class _Session:
            async def execute(self, *a, **k):
                return _Result()

        sent = {}

        async def _fake_send(self, message, subject=None, buttons=None):
            sent["message"] = message
            sent["chat"] = self.chat_id
            return True

        monkeypatch.setattr("interntrack.config.get_settings", lambda: _Settings())
        monkeypatch.setattr(
            "interntrack.services.notification_service.TelegramChannel.send",
            _fake_send,
        )
        ok = await _notify_owner_of_failure(
            _Session(),
            member_name="Skarkuzhali",
            member_email="sk@example.com",
            channel="email",
            domain_label="frontend",
        )
        assert ok is True
        assert sent["chat"] == "12345"
        assert "Skarkuzhali" in sent["message"]
        assert "sk@example.com" in sent["message"]
        assert "frontend" in sent["message"]

    @pytest.mark.asyncio
    async def test_skips_when_telegram_not_configured(self, monkeypatch):
        """No bot token → no ping (silent skip)."""
        from interntrack.scheduler.jobs import _notify_owner_of_failure

        class _Settings:
            telegram_bot_token = None
            telegram_chat_id = None
            team_owner_email = None
            is_telegram_configured = False

        class _Session:
            async def execute(self, *a, **k):
                raise AssertionError("no DB call expected")

        monkeypatch.setattr("interntrack.config.get_settings", lambda: _Settings())
        ok = await _notify_owner_of_failure(
            _Session(), member_name="X", member_email="x@x.com", channel="email"
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_skips_when_owner_has_no_chat_id(self, monkeypatch):
        """Owner without a Telegram chat id → silent skip."""
        from interntrack.scheduler.jobs import _notify_owner_of_failure

        class _Settings:
            telegram_bot_token = "bot:token"
            telegram_chat_id = "111"
            team_owner_email = None
            is_telegram_configured = True

        class _Result:
            def scalars(self):
                return self

            def all(self):
                return [_FakeOwnerUser(chat=None)]

        class _Session:
            async def execute(self, *a, **k):
                return _Result()

        monkeypatch.setattr("interntrack.config.get_settings", lambda: _Settings())
        ok = await _notify_owner_of_failure(
            _Session(), member_name="X", member_email="x@x.com", channel="email"
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_never_raises_on_db_failure(self, monkeypatch):
        """A broken session never breaks the digest pipeline."""
        from interntrack.scheduler.jobs import _notify_owner_of_failure

        class _Settings:
            telegram_bot_token = "bot:token"
            telegram_chat_id = "111"
            team_owner_email = None
            is_telegram_configured = True

        class _Session:
            async def execute(self, *a, **k):
                raise RuntimeError("db down")

        monkeypatch.setattr("interntrack.config.get_settings", lambda: _Settings())
        ok = await _notify_owner_of_failure(
            _Session(), member_name="X", member_email="x@x.com", channel="email"
        )
        assert ok is False


class TestFollowUpNudges:
    """Tests for the ⏰ stale-application follow-up nudge sweep."""

    def test_nudge_text_includes_template_and_button(self):
        """The message carries a copy-paste follow-up + View job button."""
        from interntrack.scheduler.jobs import _follow_up_nudge_text

        text, buttons = _follow_up_nudge_text(
            {
                "application_id": "a1",
                "job_title": "Security Engineer",
                "company": "Acme Corp",
                "job_url": "https://acme.example/job",
                "days_since": 8,
            }
        )
        assert "8 days" in text
        assert "Security Engineer" in text
        assert "Acme Corp" in text
        assert "check in on the status" in text
        assert buttons == [("🔗 View job", "https://acme.example/job")]

    def test_nudge_text_singular_day(self):
        """1 day renders '1 day' (not '1 days')."""
        from interntrack.scheduler.jobs import _follow_up_nudge_text

        text, _ = _follow_up_nudge_text(
            {
                "application_id": "a1",
                "job_title": "Intern",
                "company": "Co",
                "days_since": 1,
            }
        )
        assert "1 day?" in text

    def test_nudge_text_with_status_links(self):
        """With status links the nudge offers one-click updates, no dashboard."""
        from interntrack.scheduler.jobs import _follow_up_nudge_text

        links = {
            "interview": "https://api.example.com/status?u=u&a=a1&s=interview&t=tok",
            "rejected": "https://api.example.com/status?u=u&a=a1&s=rejected&t=tok",
            "offer": "https://api.example.com/status?u=u&a=a1&s=offer&t=tok",
        }
        text, buttons = _follow_up_nudge_text(
            {
                "application_id": "a1",
                "job_title": "Security Engineer",
                "company": "Acme Corp",
                "job_url": "https://acme.example/job",
                "days_since": 8,
            },
            status_links=links,
        )
        assert "Update your status right from this email" in text
        assert "update the status on your dashboard" not in text
        # _esc escapes the & in query strings inside the plain-text email.
        assert links["interview"].replace("&", "&amp;") in text
        assert links["offer"].replace("&", "&amp;") in text
        assert buttons[0] == ("🔗 View job", "https://acme.example/job")
        assert ("🗓️ Interview", links["interview"]) in buttons
        assert ("🎉 Offer", links["offer"]) in buttons

    def test_status_links_build_signed_urls(self):
        """Nudge status URLs are HMAC-bound to member + application + status."""
        from interntrack.scheduler.jobs import _status_links
        from interntrack.utils.helpers import verify_status_token

        links = _status_links("https://api.example.com", "u-1", "a-1")
        assert links is not None
        for key in ("interview", "rejected", "offer"):
            assert links[key].startswith(
                f"https://api.example.com/api/v1/email/status?u=u-1&a=a-1&s={key}&t="
            )
            token = links[key].split("&t=")[-1]
            assert verify_status_token("u-1", "a-1", key, token)
        assert _status_links("", "u-1", "a-1") is None
        assert _status_links("https://api.example.com", "", "a-1") is None
        assert _status_links("https://api.example.com", "u-1", "") is None

    @pytest.mark.asyncio
    async def test_sweep_never_raises_on_broken_session(self):
        """A DB failure yields an empty result, never an exception."""
        from interntrack.scheduler.jobs import _send_follow_up_nudges

        class _Broken:
            async def execute(self, *a, **k):
                raise RuntimeError("db down")

        result = await _send_follow_up_nudges(_Broken())
        assert result == {}
