"""Unit tests for utils/helpers.py."""

from datetime import datetime

from interntrack.utils.helpers import (
    format_currency,
    format_datetime,
    generate_id,
    slugify,
    truncate_text,
)


class TestFormatDatetime:
    """Tests for format_datetime function."""

    def test_format_datetime_with_value(self):
        """Test formatting a datetime value."""
        dt = datetime(2026, 7, 30, 14, 30)
        result = format_datetime(dt)

        assert result == "2026-07-30 14:30"

    def test_format_datetime_none(self):
        """Test formatting None value."""
        result = format_datetime(None)

        assert result == "N/A"

    def test_format_datetime_custom_format(self):
        """Test formatting with custom format string."""
        dt = datetime(2026, 7, 30, 14, 30, 45)
        result = format_datetime(dt, fmt="%Y/%m/%d %H:%M:%S")

        assert result == "2026/07/30 14:30:45"

    def test_format_datetime_date_only(self):
        """Test formatting date only."""
        dt = datetime(2026, 7, 30, 14, 30)
        result = format_datetime(dt, fmt="%Y-%m-%d")

        assert result == "2026-07-30"


class TestFormatCurrency:
    """Tests for format_currency function."""

    def test_format_currency_with_value(self):
        """Test formatting a currency value."""
        result = format_currency(50000)

        assert result == "$50,000.00 USD"

    def test_format_currency_none(self):
        """Test formatting None value."""
        result = format_currency(None)

        assert result == "N/A"

    def test_format_currency_zero(self):
        """Test formatting zero value."""
        result = format_currency(0)

        assert result == "$0.00 USD"

    def test_format_currency_custom_currency(self):
        """Test formatting with custom currency."""
        result = format_currency(1000, currency="EUR")

        assert result == "$1,000.00 EUR"

    def test_format_currency_large_number(self):
        """Test formatting large number."""
        result = format_currency(1000000)

        assert result == "$1,000,000.00 USD"

    def test_format_currency_negative(self):
        """Test formatting negative number."""
        result = format_currency(-500)

        assert result == "$-500.00 USD"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_truncate_short_text(self):
        """Test truncating text shorter than max_length."""
        result = truncate_text("Hello", max_length=10)

        assert result == "Hello"

    def test_truncate_exact_length(self):
        """Test truncating text at exact max_length."""
        result = truncate_text("Hello", max_length=5)

        assert result == "Hello"

    def test_truncate_long_text(self):
        """Test truncating text longer than max_length."""
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, max_length=20)

        assert len(result) == 20
        assert result.endswith("...")
        # max_length=20, so first 17 chars + "..."
        assert result == "This is a very lo..."

    def test_truncate_empty_string(self):
        """Test truncating empty string."""
        result = truncate_text("", max_length=10)

        assert result == ""

    def test_truncate_custom_max_length(self):
        """Test truncating with custom max_length."""
        text = "abcdefghij"
        result = truncate_text(text, max_length=7)

        assert result == "abcd..."
        assert len(result) == 7


class TestSlugify:
    """Tests for slugify function."""

    def test_slugify_simple_text(self):
        """Test slugifying simple text."""
        result = slugify("Hello World")

        assert result == "hello-world"

    def test_slugify_with_special_chars(self):
        """Test slugifying text with special characters."""
        result = slugify("Hello, World!")

        assert result == "hello-world"

    def test_slugify_with_multiple_spaces(self):
        """Test slugifying text with multiple spaces."""
        result = slugify("Hello   World")

        assert result == "hello-world"

    def test_slugify_with_underscores(self):
        """Test slugifying text with underscores."""
        result = slugify("Hello_World")

        assert result == "hello-world"

    def test_slugify_already_slug(self):
        """Test slugifying already slugified text."""
        result = slugify("hello-world")

        assert result == "hello-world"

    def test_slugify_empty_string(self):
        """Test slugifying empty string."""
        result = slugify("")

        assert result == ""

    def test_slugify_leading_trailing_spaces(self):
        """Test slugifying text with leading/trailing spaces."""
        result = slugify("  Hello World  ")

        assert result == "hello-world"


class TestMatchScoreV2:
    """Tests for match_score_v2 domain scoring."""

    def test_sqli_resume_scores_security_not_coding(self):
        """A resume listing SQLi must match the security domain, not coding.

        Regression: bare "sql" lived only in the coding/data buckets, so a
        security resume mentioning "sqli" scored as a coding candidate and
        the alerts surfaced SQL-developer jobs.
        """
        from interntrack.utils.helpers import match_score_v2

        result = match_score_v2(
            resume_skills=["sqli", "xss", "burp suite", "owasp"],
            job_tags=[],
            job_description="web application security testing",
        )
        assert result["domain"] == "security"

    def test_cybersecurity_keyword_scores_security(self):
        from interntrack.utils.helpers import match_score_v2

        result = match_score_v2(
            resume_skills=["cybersecurity", "penetration testing", "vapt"],
            job_tags=[],
            job_description="",
        )
        assert result["domain"] == "security"

    def test_pure_sql_resume_scores_coding(self):
        """A genuinely SQL-focused resume still belongs to coding/data."""
        from interntrack.utils.helpers import match_score_v2

        result = match_score_v2(
            resume_skills=["sql", "postgresql", "python"],
            job_tags=[],
            job_description="",
        )
        assert result["domain"] in ("coding", "data")


class TestGenerateId:
    """Tests for generate_id function."""

    def test_generate_id_returns_string(self):
        """Test that generate_id returns a string."""
        result = generate_id()

        assert isinstance(result, str)

    def test_generate_id_unique(self):
        """Test that generate_id returns unique values."""
        id1 = generate_id()
        id2 = generate_id()

        assert id1 != id2

    def test_generate_id_format(self):
        """Test that generate_id returns valid UUID format."""
        result = generate_id()

        # UUID format: 8-4-4-4-12 hex characters
        import re

        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, result)


class TestLocationMatches:
    """Fuzzy city matching with synonyms (Bangalore ↔ Bengaluru)."""

    def test_exact_city_in_job_location(self):
        from interntrack.utils.helpers import location_matches

        assert location_matches("bangalore, karnataka, india", "bangalore")
        assert location_matches("chennai, tamil nadu, india", "chennai")

    def test_bangalore_bengaluru_synonym(self):
        from interntrack.utils.helpers import location_matches

        # A "Bengaluru" preference matches a "Bangalore" posting and
        # vice-versa — this is what keeps per-user city digests complete.
        assert location_matches("bangalore, karnataka, india", "bengaluru")
        assert location_matches("bengaluru, karnataka, india", "bangalore")

    def test_other_city_synonyms(self):
        from interntrack.utils.helpers import location_matches

        assert location_matches("bombay, maharashtra", "mumbai")
        assert location_matches("new delhi, india", "delhi")
        assert location_matches("delhi ncr, india", "delhi")
        assert location_matches("secunderabad, telangana", "hyderabad")

    def test_short_alias_needs_word_boundary(self):
        """ "NCR" only matches as a standalone token, never inside words."""
        from interntrack.utils.helpers import location_matches

        assert location_matches("ncr, india", "delhi")
        assert not location_matches("encryption corp, mumbai", "delhi")
        assert not location_matches("incredible spaces, pune", "delhi")

    def test_wrong_city_does_not_match(self):
        from interntrack.utils.helpers import location_matches

        assert not location_matches("mumbai, maharashtra", "chennai")
        assert not location_matches("chennai, tamil nadu", "bangalore")

    def test_empty_inputs_never_match(self):
        from interntrack.utils.helpers import location_matches

        assert not location_matches("", "bangalore")
        assert not location_matches("bangalore", "")

    def test_multi_city_user_matches_any_listed_city(self):
        from interntrack.utils.helpers import location_matches

        # A user who wants "bangalore, hyderabad" gets jobs from either
        # city (comma or slash separated, synonyms included).
        assert location_matches("bangalore, karnataka", "bangalore, hyderabad")
        assert location_matches("hyderabad, telangana", "bangalore, hyderabad")
        assert location_matches("bengaluru, karnataka", "bangalore, hyderabad")
        assert location_matches("secunderabad, telangana", "bangalore, hyderabad")
        assert location_matches("hyderabad", "bangalore/hyderabad")

    def test_multi_city_user_rejects_other_cities(self):
        from interntrack.utils.helpers import location_matches

        assert not location_matches("chennai, tamil nadu", "bangalore, hyderabad")
        assert not location_matches("pune, maharashtra", "bangalore/hyderabad")


class TestIsRemoteLocation:
    """Remote / WFH / "anywhere" detection for the location gate."""

    def test_remote_markers_detected(self):
        from interntrack.utils.helpers import is_remote_location

        assert is_remote_location("Remote")
        assert is_remote_location("Work from home")
        assert is_remote_location("WFH")
        assert is_remote_location("Anywhere in India")
        assert is_remote_location("Virtual / Remote")
        assert is_remote_location("Telecommute")
        assert is_remote_location("Home-based")

    def test_city_only_is_not_remote(self):
        from interntrack.utils.helpers import is_remote_location

        assert not is_remote_location("Bangalore, Karnataka, India")
        assert not is_remote_location("Chennai, Tamil Nadu, India")

    def test_plain_hybrid_is_not_remote(self):
        """Hybrid alone still means office presence; explicit remote wins."""
        from interntrack.utils.helpers import is_remote_location

        assert not is_remote_location("Hybrid")
        assert is_remote_location("Hybrid - Remote")

    def test_empty_never_remote(self):
        from interntrack.utils.helpers import is_remote_location

        assert not is_remote_location("")
        assert not is_remote_location(None)


class TestLocationAllows:
    """City match + optional remote for the per-user location gate."""

    def test_city_match_passes_regardless_of_remote_flag(self):
        from interntrack.utils.helpers import location_allows

        assert location_allows("bangalore, karnataka", "bangalore")
        assert location_allows("bangalore, karnataka", "bangalore", False)

    def test_remote_passes_when_included(self):
        from interntrack.utils.helpers import location_allows

        assert location_allows("remote", "bangalore")
        assert location_allows("work from home", "bangalore")

    def test_remote_blocked_when_not_included(self):
        """A Chennai-only user (include_remote=False) never gets remote jobs."""
        from interntrack.utils.helpers import location_allows

        assert not location_allows("remote", "chennai", False)
        assert not location_allows("work from home", "chennai", False)

    def test_wrong_city_never_passes(self):
        from interntrack.utils.helpers import location_allows

        assert not location_allows("mumbai, maharashtra", "chennai")
        assert not location_allows("mumbai, maharashtra", "chennai", False)

    def test_empty_never_passes(self):
        from interntrack.utils.helpers import location_allows

        assert not location_allows("", "bangalore")
        assert not location_allows("bangalore", "")
