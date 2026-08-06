"""
User API schemas.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    """Registration payload — name + email identify the account."""

    name: str
    email: str
    telegram_chat_id: str | None = None
    location: str | None = None
    experience_level: str | None = None
    domains: list[str] = []
    skills: list[str] = []

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid email address")
        return email

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
    location: str | None = None
    experience_level: str | None = None
    domains: list[str] = []
    skills: list[str] = []
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
