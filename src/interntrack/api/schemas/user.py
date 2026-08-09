"""
User API schemas.
"""

import re
from datetime import datetime

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    """Registration payload — name + email identify the account."""

    name: str
    email: str
    telegram_chat_id: str | None = None
    phone_number: str | None = None
    location: str | None = None
    experience_level: str | None = None
    domains: list[str] = []
    skills: list[str] = []
    # Lowercased email of the friend whose invite link brought this user in.
    referred_by: str | None = None

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        """Normalize toward E.164; bare 10-digit numbers get the +91 default.

        Strips spaces/dashes, drops a leading national-trunk ``0``, and
        prefixes ``+91`` (India default — the product's market) when the
        user typed a bare 10-digit number. A value that reduces to nothing
        (or a lone ``+``) becomes ``None``.
        """
        if not value:
            return None
        digits = re.sub(r"[^0-9+]", "", value.strip())
        if not digits or digits == "+" or digits.count("+") > 1:
            return None
        if digits.startswith("+"):
            return digits
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10:
            return f"+91{digits}"
        return f"+{digits}"

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid email address")
        return email

    @field_validator("referred_by")
    @classmethod
    def _validate_referred_by(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip().lower()
        return email if "@" in email else None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Name is required")
        return name


class UserLogin(BaseModel):
    """Login payload — email (+ optional per-user access token).

    Accounts created after the token feature ship with an ``access_token``
    and require it here; legacy accounts without a token keep email-only
    login so nothing breaks.
    """

    email: str
    token: str | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    """Profile update payload — None fields are left unchanged."""

    name: str | None = None
    telegram_chat_id: str | None = None
    phone_number: str | None = None
    location: str | None = None
    experience_level: str | None = None
    domains: list[str] | None = None
    skills: list[str] | None = None


class UserResponse(BaseModel):
    """User profile returned by the API (never includes secrets)."""

    id: str
    name: str
    email: str
    telegram_chat_id: str | None = None
    phone_number: str | None = None
    location: str | None = None
    experience_level: str | None = None
    domains: list[str] = []
    skills: list[str] = []
    referred_by: str | None = None
    is_active: bool = True
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserAuthResponse(UserResponse):
    """Profile + the secret access token (returned only at signup/login/rotate).

    Deliberately separate from :class:`UserResponse` so the token is never
    exposed through ``GET /users`` or the list endpoint.
    """

    access_token: str


class UserListResponse(BaseModel):
    """List of user profiles."""

    users: list[UserResponse]
    total: int
