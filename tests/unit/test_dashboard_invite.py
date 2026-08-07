"""
Tests for the dashboard invite-a-friend helpers.

``dashboard.invite`` is pure Python (no Streamlit imports), so these tests
run without any Streamlit runtime.
"""

from urllib.parse import parse_qs, urlparse

from dashboard.invite import (
    KNOWN_DOMAINS,
    build_invite_link,
    count_referrals,
    invite_caption,
    parse_invite_params,
    referral_leaderboard,
    team_growth_stats,
    team_rows,
)


class TestBuildInviteLink:
    def test_builds_link_with_all_fields(self):
        url = build_invite_link(
            email="Parthasarathi@Gmail.com",
            name="Parthasarathi B",
            domains=["security", "coding"],
            location="Bengaluru, India",
        )
        parsed = urlparse(url)
        assert parsed.netloc == "cyberguide2026aug.streamlit.app"
        query = parse_qs(parsed.query)
        assert query["invite"][0] == "Parthasarathi@Gmail.com"
        assert query["ref"][0] == "Parthasarathi B"
        assert query["domains"][0] == "security,coding"
        assert query["loc"][0] == "Bengaluru, India"

    def test_unknown_domains_are_dropped(self):
        url = build_invite_link(email="a@b.com", domains=["security", "quantum"])
        query = parse_qs(urlparse(url).query)
        assert query["domains"][0] == "security"

    def test_empty_fields_produce_bare_url(self):
        url = build_invite_link()
        assert url == "https://cyberguide2026aug.streamlit.app/"
        assert "?" not in url

    def test_custom_base_url(self):
        url = build_invite_link(base_url="http://localhost:8501", email="a@b.com")
        assert url.startswith("http://localhost:8501/?invite=")

    def test_domains_lowercased_before_whitelist(self):
        url = build_invite_link(email="a@b.com", domains=["SECURITY", "Coding"])
        query = parse_qs(urlparse(url).query)
        assert query["domains"][0] == "security,coding"


class TestParseInviteParams:
    def test_parses_string_values(self):
        result = parse_invite_params(
            {
                "invite": "friend@mail.com",
                "ref": "Parthasarathi B",
                "domains": "security,coding",
                "loc": "Bengaluru",
            }
        )
        assert result == {
            "invite": "friend@mail.com",
            "ref": "Parthasarathi B",
            "domains": ["security", "coding"],
            "location": "Bengaluru",
        }

    def test_accepts_list_values(self):
        result = parse_invite_params(
            {"invite": ["friend@mail.com"], "domains": ["security", "data"]}
        )
        assert result["invite"] == "friend@mail.com"
        assert result["domains"] == ["security", "data"]

    def test_unknown_domains_become_all(self):
        result = parse_invite_params({"domains": "quantum,alchemy"})
        assert result["domains"] == ["all"]

    def test_invalid_email_ignored(self):
        result = parse_invite_params({"invite": "not-an-email", "ref": "x"})
        assert "invite" not in result
        assert result["ref"] == "x"

    def test_empty_input_returns_empty_dict(self):
        assert parse_invite_params({}) == {}
        assert parse_invite_params({"invite": ""}) == {}

    def test_domains_restricted_to_known_keys(self):
        result = parse_invite_params({"domains": "security,OTHER"})
        assert set(result["domains"]).issubset(KNOWN_DOMAINS)

    def test_round_trip_build_then_parse(self):
        url = build_invite_link(
            email="a@b.com",
            domains=["security", "coding"],
            location="Bengaluru",
        )
        raw = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        result = parse_invite_params(raw)
        assert result["invite"] == "a@b.com"
        assert result["domains"] == ["security", "coding"]
        assert result["location"] == "Bengaluru"


class TestInviteCaption:
    def test_with_referrer_and_domains(self):
        caption = invite_caption(
            {"ref": "Parthasarathi B", "domains": ["security", "coding"]}
        )
        assert caption is not None
        assert "Parthasarathi B" in caption
        assert "security, coding" in caption

    def test_all_domains_omit_list(self):
        caption = invite_caption({"ref": "X", "domains": ["all"]})
        assert caption == "Invited by **X**"

    def test_empty_invite_returns_none(self):
        assert invite_caption({}) is None
        assert invite_caption({"domains": []}) is None


class TestCountReferrals:
    _USERS = [
        {"email": "a@b.com", "referred_by": "me@x.com"},
        {"email": "c@d.com", "referred_by": "ME@X.com"},  # case-insensitive
        {"email": "e@f.com", "referred_by": "other@x.com"},
        {"email": "g@h.com", "referred_by": None},
    ]

    def test_counts_only_own_referrals_case_insensitive(self):
        assert count_referrals(self._USERS, "me@x.com") == 2
        assert count_referrals(self._USERS, "ME@X.COM") == 2

    def test_no_matches_returns_zero(self):
        assert count_referrals(self._USERS, "nobody@x.com") == 0

    def test_empty_referrer_returns_zero(self):
        assert count_referrals(self._USERS, None) == 0
        assert count_referrals(self._USERS, "") == 0

    def test_own_account_never_counts_as_self_referral(self):
        users = [
            {"email": "me@x.com", "referred_by": None},
            {"email": "me@x.com", "referred_by": "me@x.com"},  # self-referral
            {"email": "friend@x.com", "referred_by": "me@x.com"},
        ]
        assert count_referrals(users, "me@x.com") == 1


class TestTeamRows:
    _USERS = [
        {
            "name": "Me",
            "email": "me@x.com",
            "location": "Bengaluru",
            "domains": ["security"],
            "created_at": "2026-08-01T10:00:00",
            "referred_by": None,
        },
        {
            "name": "Friend",
            "email": "f@x.com",
            "location": "Hyderabad",
            "domains": ["data", "coding"],
            "created_at": "2026-08-02T10:00:00",
            "referred_by": "me@x.com",
        },
    ]

    def test_flags_me_and_referrals(self):
        rows = team_rows(self._USERS, me_email="me@x.com")
        by_email = {r["email"]: r for r in rows}
        assert by_email["me@x.com"]["is_me"] is True
        assert by_email["me@x.com"]["referred_by_me"] is False
        assert by_email["f@x.com"]["referred_by_me"] is True
        assert by_email["f@x.com"]["is_me"] is False

    def test_sorts_newest_first(self):
        rows = team_rows(self._USERS)
        assert [r["email"] for r in rows] == ["f@x.com", "me@x.com"]

    def test_case_insensitive_me_match(self):
        rows = team_rows(self._USERS, me_email="ME@X.COM")
        by_email = {r["email"]: r for r in rows}
        assert by_email["me@x.com"]["is_me"] is True

    def test_markdown_injection_is_stripped(self):
        caption = invite_caption({"ref": "[Click](http://evil.com) **bold**"})
        assert caption is not None
        # The referrer text is sanitized — no markdown/HTML syntax survives,
        # so the URL is inert plain text (the ** are the caption's own wrap).
        assert "[Click]" not in caption
        assert "](http" not in caption
        assert "Clickhttp://evil.com bold" in caption

    def test_referrer_email_is_sanitized(self):
        caption = invite_caption({"invite": "a@b.com <img src=x>"})
        assert caption is not None
        assert "<img" not in caption
        assert "a@b.com" in caption


class TestReferralLeaderboard:
    _USERS = [
        {"email": "a@x.com", "name": "A", "referred_by": "me@x.com"},
        {"email": "b@x.com", "name": "B", "referred_by": "ME@X.com"},
        {"email": "c@x.com", "name": "C", "referred_by": "other@x.com"},
        {"email": "d@x.com", "name": "D", "referred_by": "other@x.com"},
        {"email": "e@x.com", "name": "E", "referred_by": None},
    ]

    def test_ranks_by_count_desc_case_insensitive(self):
        board = referral_leaderboard(self._USERS)
        assert [row["count"] for row in board] == [2, 2]
        # me@x.com grouped case-insensitively (a@ + b@ both referred by it).
        assert {row["email"] for row in board} == {"me@x.com", "other@x.com"}

    def test_uneven_counts_order_desc(self):
        users = [
            {"email": "a@x.com", "name": "A", "referred_by": "low@x.com"},
            {"email": "b@x.com", "name": "B", "referred_by": "high@x.com"},
            {"email": "c@x.com", "name": "C", "referred_by": "high@x.com"},
            {"email": "d@x.com", "name": "D", "referred_by": "high@x.com"},
        ]
        board = referral_leaderboard(users)
        assert board[0]["email"] == "high@x.com"
        assert board[0]["count"] == 3
        assert board[1]["email"] == "low@x.com"

    def test_excludes_referrers_with_no_matches(self):
        users = [{"email": "x@x.com", "name": "X", "referred_by": None}]
        assert referral_leaderboard(users) == []

    def test_limit_caps_board(self):
        board = referral_leaderboard(self._USERS, limit=1)
        assert len(board) == 1


class TestTeamGrowthStats:
    _BASE = {"email": "me@x.com", "name": "Me", "referred_by": None}

    def test_counts_team_and_recent_joiners(self):
        users = [
            self._BASE,
            {
                "email": "f@x.com",
                "name": "F",
                "referred_by": "me@x.com",
                "created_at": "2026-08-01T10:00:00+00:00",
            },
        ]
        stats = team_growth_stats(users, "me@x.com")
        assert stats["team_size"] == 2
        # Only the friend has a created_at timestamp -> 1 recent joiner.
        assert stats["joined_recently"] == 1
        assert stats["my_referrals"] == 1
        assert stats["referrals_recently"] == 1

    def test_old_joiners_not_recent(self):
        users = [
            self._BASE,
            {"email": "old@x.com", "name": "Old", "created_at": "2020-01-01T00:00:00"},
        ]
        stats = team_growth_stats(users)
        assert stats["joined_recently"] == 0

    def test_excludes_self_referral(self):
        users = [
            self._BASE,
            {"email": "me@x.com", "name": "Me", "referred_by": "me@x.com"},
        ]
        stats = team_growth_stats(users, "me@x.com")
        assert stats["my_referrals"] == 0

    def test_missing_dates_never_crash(self):
        users = [
            {
                "email": "a@x.com",
                "name": "A",
                "referred_by": "me@x.com",
                "created_at": "not-a-date",
            }
        ]
        stats = team_growth_stats(users, "me@x.com")
        assert stats["my_referrals"] == 1
        assert stats["referrals_recently"] == 0
