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
        dt = datetime(2026, 7, 15, 14, 30, 0)
        result = format_datetime(dt)
        assert result == "2026-07-15 14:30"

    def test_format_datetime_none(self):
        result = format_datetime(None)
        assert result == "N/A"

    def test_format_datetime_custom_format(self):
        dt = datetime(2026, 7, 15, 14, 30, 0)
        result = format_datetime(dt, fmt="%d/%m/%Y")
        assert result == "15/07/2026"

    def test_format_datetime_time_only(self):
        dt = datetime(2026, 7, 15, 14, 30, 0)
        result = format_datetime(dt, fmt="%H:%M")
        assert result == "14:30"


class TestFormatCurrency:
    """Tests for format_currency function."""

    def test_format_currency_with_value(self):
        result = format_currency(50000)
        assert result == "$50,000.00 USD"

    def test_format_currency_none(self):
        result = format_currency(None)
        assert result == "N/A"

    def test_format_currency_custom_currency(self):
        result = format_currency(1000, currency="EUR")
        assert result == "$1,000.00 EUR"

    def test_format_currency_large_number(self):
        result = format_currency(1000000)
        assert result == "$1,000,000.00 USD"

    def test_format_currency_zero(self):
        result = format_currency(0)
        assert result == "$0.00 USD"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_short_text(self):
        result = truncate_text("hello", max_length=10)
        assert result == "hello"

    def test_exact_length(self):
        result = truncate_text("hello", max_length=5)
        assert result == "hello"

    def test_long_text(self):
        result = truncate_text("hello world", max_length=8)
        assert result == "hello..."

    def test_default_max_length(self):
        text = "a" * 150
        result = truncate_text(text)
        assert len(result) == 100
        assert result.endswith("...")

    def test_empty_string(self):
        result = truncate_text("")
        assert result == ""


class TestSlugify:
    """Tests for slugify function."""

    def test_simple_text(self):
        result = slugify("Hello World")
        assert result == "hello-world"

    def test_special_characters(self):
        result = slugify("Hello, World! @#$%")
        assert result == "hello-world"

    def test_multiple_spaces(self):
        result = slugify("hello   world")
        assert result == "hello-world"

    def test_leading_trailing_spaces(self):
        result = slugify("  hello  ")
        assert result == "hello"

    def test_underscores(self):
        result = slugify("hello_world")
        assert result == "hello-world"

    def test_empty_string(self):
        result = slugify("")
        assert result == ""


class TestGenerateId:
    """Tests for generate_id function."""

    def test_generates_string(self):
        result = generate_id()
        assert isinstance(result, str)

    def test_generates_uuid_format(self):
        result = generate_id()
        parts = result.split("-")
        assert len(parts) == 5

    def test_unique_ids(self):
        id1 = generate_id()
        id2 = generate_id()
        assert id1 != id2
