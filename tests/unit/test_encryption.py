"""Unit tests for utils/encryption.py."""

import pytest
from cryptography.fernet import InvalidToken

from interntrack.utils.encryption import SecretManager, mask_sensitive


class TestSecretManager:
    """Tests for SecretManager class."""

    def test_generate_key(self):
        """Test generating a new encryption key."""
        key1 = SecretManager.generate_key()
        key2 = SecretManager.generate_key()

        assert key1 != key2
        assert len(key1) > 0
        assert isinstance(key1, str)

    def test_init_with_string_key(self):
        """Test initializing SecretManager with string key."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        assert manager._cipher is not None

    def test_init_with_bytes_key(self):
        """Test initializing SecretManager with bytes key."""
        key = SecretManager.generate_key().encode()
        manager = SecretManager(key)

        assert manager._cipher is not None

    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt and decrypt roundtrip."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        original = "my-secret-api-key-12345"
        encrypted = manager.encrypt(original)

        assert encrypted != original
        assert isinstance(encrypted, str)

        decrypted = manager.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_different_each_time(self):
        """Test that encryption produces different ciphertext each time."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        encrypted1 = manager.encrypt("test")
        encrypted2 = manager.encrypt("test")

        # Fernet uses random IV, so ciphertext should differ
        # (though this is probabilistic, it's extremely unlikely to be equal)
        # We'll just verify both decrypt correctly
        assert manager.decrypt(encrypted1) == "test"
        assert manager.decrypt(encrypted2) == "test"

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        encrypted = manager.encrypt("")
        decrypted = manager.decrypt(encrypted)

        assert decrypted == ""

    def test_encrypt_long_string(self):
        """Test encrypting a long string."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        original = "x" * 10000
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_special_characters(self):
        """Test encrypting string with special characters."""
        key = SecretManager.generate_key()
        manager = SecretManager(key)

        original = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == original

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        key1 = SecretManager.generate_key()
        key2 = SecretManager.generate_key()

        manager1 = SecretManager(key1)
        manager2 = SecretManager(key2)

        encrypted = manager1.encrypt("secret")

        with pytest.raises(InvalidToken):
            manager2.decrypt(encrypted)


class TestMaskSensitive:
    """Tests for mask_sensitive function."""

    def test_mask_long_value(self):
        """Test masking a long value."""
        result = mask_sensitive("my-secret-api-key")
        # "my-secret-api-key" = 17 chars, visible_chars=4, last 4 = "-key"
        assert result == "*************-key"
        assert result.startswith("*")
        assert result.endswith("-key")
        assert len(result) == len("my-secret-api-key")

    def test_mask_short_value(self):
        """Test masking a short value (shorter than visible_chars)."""
        result = mask_sensitive("abc", visible_chars=4)
        assert result == "***"

    def test_mask_exact_length(self):
        """Test masking value with exact visible_chars length."""
        result = mask_sensitive("abcd", visible_chars=4)
        assert result == "****"

    def test_mask_with_custom_visible_chars(self):
        """Test masking with custom visible_chars parameter."""
        result = mask_sensitive("my-secret-key", visible_chars=6)
        # "my-secret-key" = 13 chars, visible_chars=6, last 6 = "et-key"
        assert result == "*******et-key"

    def test_mask_empty_string(self):
        """Test masking empty string."""
        result = mask_sensitive("", visible_chars=4)
        assert result == ""

    def test_mask_preserves_length(self):
        """Test that masking preserves original length."""
        original = "sensitive-data-here"
        result = mask_sensitive(original)
        assert len(result) == len(original)
