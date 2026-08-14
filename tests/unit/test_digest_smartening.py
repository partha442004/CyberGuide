"""Unit tests for digest smartening: salary-target chips + keyword highlights."""

from unittest.mock import AsyncMock, MagicMock


def _job(**overrides):
    """A minimal job dict as the digest builders see it."""
    return {
        "title": "SOC Analyst",
        "company": "Cyber Corp",
        "location": "Bangalore",
        "url": "https://example.com/job",
        "description": "Monitor SIEM alerts and respond to incidents.",
        "tags": ["security", "soc"],
        "required_skills": ["Splunk", "SIEM"],
        "salary_min": 800000,
        "salary_max": 1200000,
        "salary_currency": "INR",
        "age_days": 1,
        **overrides,
    }


class TestSalaryMeetsTarget:
    # Targets are stored as absolute annual INR (e.g. 8 LPA = 800000).
    def test_no_target_never_meets(self):
        from interntrack.scheduler.jobs import _salary_meets_target

        assert _salary_meets_target(_job(salary_min=900000), None) is False
        assert _salary_meets_target(_job(salary_min=900000), 0) is False

    def test_inr_target_met(self):
        from interntrack.scheduler.jobs import _salary_meets_target

        assert _salary_meets_target(_job(salary_min=900000), 800000) is True
        assert _salary_meets_target(_job(salary_min=600000), 800000) is False

    def test_uses_minimum_not_maximum(self):
        from interntrack.scheduler.jobs import _salary_meets_target

        # Min below target but max above: still below the target.
        assert (
            _salary_meets_target(_job(salary_min=600000, salary_max=1200000), 800000)
            is False
        )

    def test_usd_postings_compared_against_inr_target(self):
        from interntrack.scheduler.jobs import _salary_meets_target

        # 100k USD ~= 8.3M INR, well above an 8 LPA (800000) target.
        assert (
            _salary_meets_target(_job(salary_min=100000, salary_currency="USD"), 800000)
            is True
        )

    def test_missing_salary_never_meets(self):
        from interntrack.scheduler.jobs import _salary_meets_target

        assert (
            _salary_meets_target(_job(salary_min=None, salary_max=None), 800000)
            is False
        )

    def test_bad_values_never_raise(self):
        from interntrack.scheduler.jobs import _salary_meets_target

        assert _salary_meets_target(_job(salary_min="n/a"), 800000) is False
        assert _salary_meets_target(_job(salary_min=None), "garbage") is False


class TestSalaryBelowFloor:
    def test_no_floor_never_drops(self):
        from interntrack.scheduler.jobs import _salary_below_floor

        assert _salary_below_floor(_job(salary_min=100000), None) is False
        assert _salary_below_floor(_job(salary_min=100000), 0) is False

    def test_below_floor_dropped(self):
        from interntrack.scheduler.jobs import _salary_below_floor

        assert _salary_below_floor(_job(salary_min=600000), 800000) is True
        assert _salary_below_floor(_job(salary_min=800000), 800000) is False
        assert _salary_below_floor(_job(salary_min=900000), 800000) is False

    def test_unknown_salary_kept(self):
        """No salary data must never drop a job — freshers lose nothing."""
        from interntrack.scheduler.jobs import _salary_below_floor

        assert (
            _salary_below_floor(_job(salary_min=None, salary_max=None), 800000) is False
        )

    def test_uses_minimum_not_maximum(self):
        from interntrack.scheduler.jobs import _salary_below_floor

        # Min below the floor but max above: still dropped.
        assert (
            _salary_below_floor(_job(salary_min=600000, salary_max=1200000), 800000)
            is True
        )

    def test_usd_postings_compared_against_inr_floor(self):
        from interntrack.scheduler.jobs import _salary_below_floor

        # 5k USD ~= 415k INR, below an 8 LPA floor → dropped.
        assert (
            _salary_below_floor(_job(salary_min=5000, salary_currency="USD"), 800000)
            is True
        )

    def test_bad_values_never_raise(self):
        from interntrack.scheduler.jobs import _salary_below_floor

        assert _salary_below_floor(_job(salary_min="n/a"), 800000) is False
        assert _salary_below_floor(_job(salary_min=None), "garbage") is False


class TestKeywordHits:
    def test_empty_keywords_returns_nothing(self):
        from interntrack.scheduler.jobs import _keyword_hits

        assert _keyword_hits(_job(), None) == []
        assert _keyword_hits(_job(), []) == []

    def test_title_and_skills_match(self):
        from interntrack.scheduler.jobs import _keyword_hits

        hits = _keyword_hits(_job(), ["splunk", "vapt", "python"])
        assert hits == ["splunk"]

    def test_description_match_case_insensitive(self):
        from interntrack.scheduler.jobs import _keyword_hits

        hits = _keyword_hits(
            _job(description="INCIDENT RESPONSE is the core duty"),
            ["Incident Response"],
        )
        assert hits == ["incident response"]

    def test_capped_at_three(self):
        from interntrack.scheduler.jobs import _keyword_hits

        hits = _keyword_hits(
            _job(
                description="splunk siem linux python windows burp",
                tags=[],
                required_skills=[],
            ),
            ["splunk", "siem", "linux", "python", "burp"],
        )
        assert len(hits) == 3

    def test_bad_keywords_never_raise(self):
        from interntrack.scheduler.jobs import _keyword_hits

        assert _keyword_hits(_job(), ["", "   ", None]) == []


class TestJobLinesMarkers:
    def test_salary_target_line_appears(self):
        from interntrack.scheduler.jobs import _job_lines

        lines = _job_lines(
            80.0, _job(salary_min=900000), target_salary=800000, keywords=None
        )
        assert any("Meets your target salary" in line for line in lines)

    def test_keyword_marker_line_appears(self):
        from interntrack.scheduler.jobs import _job_lines

        lines = _job_lines(
            80.0,
            _job(required_skills=["Splunk", "SIEM"]),
            target_salary=None,
            keywords=["splunk"],
        )
        assert any("Matches: splunk" in line for line in lines)

    def test_no_markers_without_prefs(self):
        from interntrack.scheduler.jobs import _job_lines

        lines = _job_lines(80.0, _job(), target_salary=None, keywords=[])
        assert not any("Meets your target salary" in line for line in lines)
        assert not any("Matches:" in line for line in lines)


class TestApiPutPrefs:
    """PUT /notifications/preferences/{user_id} persists the new fields."""

    def test_min_salary_and_keywords_saved(self):
        from interntrack.api.schemas.notification import (
            AlertPreferencesUpdate,
        )
        from interntrack.api.v1.notifications import update_alert_preferences

        pref = MagicMock()
        pref.domains = ["security"]
        pref.channels = ["email"]
        pref.min_match_score = 60
        pref.is_enabled = True
        pref.last_alert_at = None
        pref.slot_domains = {}
        pref.weekly_enabled = True
        pref.instant_alerts = True
        pref.include_remote = True
        pref.quiet_day_emails = True
        pref.paused_until = None
        pref.min_salary = None
        pref.keywords = []
        pref.user_id = "userX"

        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = pref
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        update = AlertPreferencesUpdate(
            min_salary=12, keywords=[" Splunk ", "splunk", "vapt"]
        )
        asyncio_run(update_alert_preferences("userX", update, session))
        assert pref.min_salary == 12
        assert pref.keywords == ["splunk", "vapt"]  # stripped, lowercased, deduped
        session.commit.assert_awaited_once()

    def test_schema_accepts_new_fields(self):
        from interntrack.api.schemas.notification import (
            AlertPreferencesUpdate,
        )

        update = AlertPreferencesUpdate(min_salary=12, keywords=["Splunk", "VAPT"])
        assert update.min_salary == 12
        assert update.keywords == ["Splunk", "VAPT"]
        # None keeps current values.
        assert AlertPreferencesUpdate().min_salary is None
        assert AlertPreferencesUpdate().keywords is None


def asyncio_run(coro):
    """Run a coroutine on a fresh event loop (avoids pytest-asyncio drift)."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
