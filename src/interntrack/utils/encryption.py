"""
Encryption utilities for sensitive data.
"""

from cryptography.fernet import Fernet


class SecretManager:
    """Manage encryption for sensitive configuration."""

    def __init__(self, key: str | bytes):
        """Initialize with encryption key."""
        if isinstance(key, str):
            key = key.encode()
        self._cipher = Fernet(key)

    def encrypt(self, value: str) -> str:
        """Encrypt a string value."""
        return self._cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt an encrypted value."""
        return self._cipher.decrypt(encrypted.encode()).decode()

    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key."""
        return Fernet.generate_key().decode()


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive value showing only last characters."""
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
