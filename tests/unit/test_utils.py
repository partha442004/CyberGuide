"""
Unit tests for utility functions.
"""

import pytest
from datetime import datetime

from interntrack.utils.helpers import (
    format_datetime,
    format_currency,
    truncate_text,
    slugify,
    generate_id,
)
from interntrack.utils.encryption import SecretManager, mask_sensitive


class TestHelpers:
    """Tests for helper functions."""

    def test_format_datetime_with_value(self):
        """Test format_datetime with a datetime value."""
        dt = datetime(2026, 7, 30, 14, 30, 0)
        result = format_datetime(dt)

        assert result == "2026-07-30 14:30"

    def test_format_datetime_with_none(self):
        """Test format_datetime with None."""
        result = format_datetime(None)

        assert result == "N/A"

    def test_format_datetime_custom_format(self):
        """Test format_datetime with custom format."""
        dt = datetime(2026, 7, 30, 14, 30, 0)
        result = format_datetime(dt, "%Y/%m/%d")

        assert result == "2026/07/30"

    def test_format_currency_with_value(self):
        """Test format_currency with a value."""
        result = format_currency(85000)

        assert "$85,000.00 USD" in result

    def test_format_currency_with_none(self):
        """Test format_currency with None."""
        result = format_currency(None)

        assert result == "N/A"

    def test_format_currency_custom_currency(self):
        """Test format_currency with custom currency."""
        result = format_currency(50000, "EUR")

        assert "EUR" in result

    def test_truncate_text_short(self):
        """Test truncate_text with short text."""
        result = truncate_text("Hello", 10)

        assert result == "Hello"

    def test_truncate_text_long(self):
        """Test truncate_text with long text."""
        result = truncate_text("Hello World, this is a long text", 10)

        assert len(result) == 10
        assert result.endswith("...")

    def test_slugify(self):
        """Test slugify function."""
        result = slugify("Hello World!")

        assert result == "hello-world"

    def test_slugify_special_chars(self):
        """Test slugify with special characters."""
        result = slugify("Python Developer @ TechCorp")

        assert result == "python-developer-techcorp"

    def test_generate_id_unique(self):
        """Test generate_id returns unique values."""
        id1 = generate_id()
        id2 = generate_id()

        assert id1 != id2
        assert len(id1) == 36  # UUID format


class TestEncryption:
    """Tests for encryption utilities."""

    def test_encrypt_decrypt(self):
        """Test encrypt and decrypt roundtrip."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        original = "my-secret-api-key"
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_mask_sensitive_short(self):
        """Test mask_sensitive with short value."""
        result = mask_sensitive("abc")

        assert result == "***"

    def test_mask_sensitive_long(self):
        """Test mask_sensitive with long value."""
        result = mask_sensitive("abcdefghijklmnop")

        assert result.endswith("mnop")
        assert result.startswith("***")
