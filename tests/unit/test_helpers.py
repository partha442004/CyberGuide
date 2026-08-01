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
