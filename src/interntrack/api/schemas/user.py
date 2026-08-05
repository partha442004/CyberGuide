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
    """Login payload — email only (no password per product decision)."""

    email: str

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


class UserListResponse(BaseModel):
    """List of user profiles."""

    users: list[UserResponse]
    total: int
