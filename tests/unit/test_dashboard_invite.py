"""
Tests for the dashboard invite-a-friend helpers.

``dashboard.invite`` is pure Python (no Streamlit imports), so these tests
run without any Streamlit runtime.
"""

from urllib.parse import parse_qs, urlparse

from dashboard.invite import (
    KNOWN_DOMAINS,
    build_invite_link,
    invite_caption,
    parse_invite_params,
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
