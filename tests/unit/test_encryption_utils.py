"""Unit tests for utils/encryption.py."""

import pytest

from interntrack.utils.encryption import SecretManager, mask_sensitive


class TestSecretManager:
    """Tests for SecretManager class."""

    def test_init_with_string_key(self):
        key = SecretManager.generate_key()
        sm = SecretManager(key)
        assert sm._cipher is not None

    def test_init_with_bytes_key(self):
        key = SecretManager.generate_key().encode()
        sm = SecretManager(key)
        assert sm._cipher is not None

    def test_generate_key(self):
        key = SecretManager.generate_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_generate_key_unique(self):
        key1 = SecretManager.generate_key()
        key2 = SecretManager.generate_key()
        assert key1 != key2

    def test_encrypt_decrypt(self):
        key = SecretManager.generate_key()
        sm = SecretManager(key)

        original = "sensitive-data-123"
        encrypted = sm.encrypt(original)
        decrypted = sm.decrypt(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_encrypt_returns_string(self):
        key = SecretManager.generate_key()
        sm = SecretManager(key)
        result = sm.encrypt("test")
        assert isinstance(result, str)

    def test_decrypt_returns_string(self):
        key = SecretManager.generate_key()
        sm = SecretManager(key)
        encrypted = sm.encrypt("test")
        result = sm.decrypt(encrypted)
        assert isinstance(result, str)

    def test_encrypt_empty_string(self):
        key = SecretManager.generate_key()
        sm = SecretManager(key)
        encrypted = sm.encrypt("")
        decrypted = sm.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_unicode(self):
        key = SecretManager.generate_key()
        sm = SecretManager(key)
        original = "Hello 世界 🌍"
        encrypted = sm.encrypt(original)
        decrypted = sm.decrypt(encrypted)
        assert decrypted == original

    def test_different_keys_cant_decrypt(self):
        key1 = SecretManager.generate_key()
        key2 = SecretManager.generate_key()
        sm1 = SecretManager(key1)
        sm2 = SecretManager(key2)

        encrypted = sm1.encrypt("secret")
        with pytest.raises(Exception):
            sm2.decrypt(encrypted)


class TestMaskSensitive:
    """Tests for mask_sensitive function."""

    def test_mask_long_value(self):
        result = mask_sensitive("abcdefghijklmnop")
        assert result.startswith("*")
        assert result.endswith("mnop")
        assert len(result) == 16

    def test_mask_short_value(self):
        result = mask_sensitive("abc")
        assert result == "***"

    def test_mask_exact_length(self):
        result = mask_sensitive("abcd", visible_chars=4)
        assert result == "****"

    def test_mask_custom_visible(self):
        result = mask_sensitive("abcdefghij", visible_chars=2)
        assert result.endswith("ij")
        assert len(result) == 10

    def test_mask_single_char(self):
        result = mask_sensitive("x")
        assert result == "*"

    def test_mask_empty_string(self):
        result = mask_sensitive("")
        assert result == ""
