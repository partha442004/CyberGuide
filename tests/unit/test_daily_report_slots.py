"""
Regression tests for per-user slot domain resolution in the daily report.

A user's saved domain preference must never be silently replaced by the
slot default on scheduled sends — otherwise a "frontend" user gets
"coding" (or worse) and their digest is always empty.
"""


class TestResolveSlotDomains:
    def _resolve(self, prefs: dict, slot: str | None):
        from interntrack.api.v1.reports import _resolve_slot_domains

        return _resolve_slot_domains(prefs, slot)

    def test_no_slot_leaves_domains_untouched(self):
        assert (
            self._resolve({"domains": ["frontend"], "slot_domains": {}}, None) is None
        )

    def test_per_slot_override_wins(self):
        prefs = {
            "domains": ["frontend"],
            "slot_domains": {"afternoon": ["data"]},
        }
        assert self._resolve(prefs, "afternoon") == ["data"]

    def test_saved_domains_beat_slot_default(self):
        """The regression: frontend user must not be switched to 'coding'."""
        prefs = {"domains": ["frontend"], "slot_domains": {}}
        assert self._resolve(prefs, "afternoon") == ["frontend"]
        assert self._resolve(prefs, "morning") == ["frontend"]
        assert self._resolve(prefs, "evening") == ["frontend"]

    def test_no_preference_falls_back_to_slot_default(self):
        prefs = {"domains": None, "slot_domains": {}}
        assert self._resolve(prefs, "morning") == ["security"]
        assert self._resolve(prefs, "afternoon") == ["coding"]

    def test_unknown_slot_returns_none(self):
        assert self._resolve({"domains": None, "slot_domains": {}}, "midnight") is None

    def test_empty_slot_override_falls_through(self):
        prefs = {"domains": ["frontend"], "slot_domains": {"afternoon": []}}
        assert self._resolve(prefs, "afternoon") == ["frontend"]

    async def test_daily_report_widens_when_empty(self, monkeypatch):
        """The production cron path must auto-widen an empty digest.

        Regression: the GitHub Actions cron calls ``/reports/daily`` (not
        the APScheduler worker, which never runs on Vercel), so the widen
        fallback has to live in this endpoint too — otherwise every member
        gets "no new jobs" emails even when a wider window would find roles.
        """
        from interntrack.api.v1 import reports as reports_api
        from interntrack.api.v1.reports import get_daily_report

        empty = {"new_jobs": [], "summary": {"new_jobs": 0}}
        widened = {
            "new_jobs": [{"id": "j1", "title": "Railway RRB"}],
            "widen_note": "location",
        }

        async def fake_generate(self, **kwargs):
            return empty

        async def fake_sent_urls(db, user_id):
            return set()

        async def fake_widened(service, **kwargs):
            return widened

        async def fake_send(db, prefs, report, **kwargs):
            return {"email": True}

        async def fake_targets(db):
            return [
                {
                    "user_id": "u1",
                    "prefs": {"domains": ["govt"], "is_enabled": True},
                    "user": None,
                }
            ]

        monkeypatch.setattr(reports_api, "_load_digest_targets", fake_targets)
        monkeypatch.setattr(
            reports_api.ReportService, "generate_daily_report", fake_generate
        )
        monkeypatch.setattr(reports_api, "_send_alert_digest", fake_send)

        import interntrack.scheduler.jobs as jobs

        async def fake_mark(db, uid):
            return None

        monkeypatch.setattr(jobs, "_mark_alert_sent", fake_mark)
        monkeypatch.setattr(jobs, "_sent_urls_for", fake_sent_urls)
        monkeypatch.setattr(jobs, "_widened_report", fake_widened)

        captured = {}

        async def fake_send_quiet(db, prefs, **kwargs):
            captured["quiet"] = True

        monkeypatch.setattr(reports_api, "_send_quiet_day_digest", fake_send_quiet)

        result = await get_daily_report(db=None, slot="morning", preview=False)
        # The widened report (with jobs) replaced the empty one, so the real
        # digest send fired — not the quiet-day "no jobs" email.
        assert "quiet" not in captured
        assert (result.get("new_jobs") or []) == widened["new_jobs"]
        assert result.get("widen_note") == "location"
