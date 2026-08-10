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
