"""
Users API — registration, login (by email) and profile management.

Each registered user gets their own ``AlertPreferences`` row (auto-enabled
with the domains they picked at signup and whatever channels the API has
configured), so the daily digest, match scoring and notification history are
personalized per user. Login is email-only (no password) per the product
decision; the returned ``user_id`` is stored in the dashboard session.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.user import (
    UserAuthResponse,
    UserCreate,
    UserListResponse,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from interntrack.api.v1.notifications import _normalize_domains
from interntrack.config import get_settings
from interntrack.database.session import get_db
from interntrack.domain.models import AlertPreferences, User

router = APIRouter()

_EXPERIENCE_LEVELS = ("fresher", "intern", "junior", "senior")


def _configured_channels() -> list[str]:
    """The notification channels the API can actually deliver through."""
    settings = get_settings()
    channels = []
    if settings.is_telegram_configured:
        channels.append("telegram")
    if settings.is_email_configured:
        channels.append("email")
    if settings.is_discord_configured:
        channels.append("discord")
    if settings.is_slack_configured:
        channels.append("slack")
    return channels


async def _get_user_or_404(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _new_access_token() -> str:
    """Cryptographically random secret token for an account."""
    return secrets.token_urlsafe(32)


@router.post("/register", response_model=UserAuthResponse, status_code=201)
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create an account and auto-enable daily alerts for this user.

    The user's chosen domains and the API's configured channels are saved
    into a fresh ``AlertPreferences`` row, so personalized digests start
    immediately. The response includes the account's secret ``access_token``
    (shown once) — login requires it from now on. Returns 409 when the
    email is already registered.
    """
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists — log in instead",
        )

    experience = payload.experience_level
    if experience and experience not in _EXPERIENCE_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"experience_level must be one of {', '.join(_EXPERIENCE_LEVELS)}",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        telegram_chat_id=payload.telegram_chat_id or None,
        location=payload.location or None,
        experience_level=experience or None,
        domains=_normalize_domains(payload.domains),
        skills=[str(s).strip() for s in payload.skills if str(s).strip()],
        is_active=True,
        access_token=_new_access_token(),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # A concurrent registration with the same email hit the unique index.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists — log in instead",
        ) from None

    # Auto-enable personalized alerts with the chosen domains + channels.
    db.add(
        AlertPreferences(
            user_id=user.id,
            domains=_normalize_domains(payload.domains),
            channels=_configured_channels(),
            is_enabled=True,
        )
    )
    await db.commit()
    await db.refresh(user)
    return UserAuthResponse.model_validate(user)


@router.post("/login", response_model=UserAuthResponse)
async def login_user(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Look up a profile by email (+ per-user access token when set)."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email — register first",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")
    if user.access_token and not secrets.compare_digest(
        str(user.access_token),
        payload.token or "",
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing access token",
        )
    return UserAuthResponse.model_validate(user)


@router.post("/{user_id}/rotate-token", response_model=UserAuthResponse)
async def rotate_user_token(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Replace the account's secret token (old one stops working)."""
    user = await _get_user_or_404(db, user_id)
    user.access_token = _new_access_token()  # type: ignore[assignment]
    await db.commit()
    await db.refresh(user)
    return UserAuthResponse.model_validate(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
):
    """List registered user profiles (newest first)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(200))
    users = result.scalars().all()
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=len(users),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get one user's profile."""
    user = await _get_user_or_404(db, user_id)
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update profile fields (only provided ones are changed)."""
    user = await _get_user_or_404(db, user_id)
    if update.name is not None:
        user.name = update.name.strip()  # type: ignore[assignment]
    if update.telegram_chat_id is not None:
        user.telegram_chat_id = update.telegram_chat_id or None  # type: ignore[assignment]
    if update.location is not None:
        user.location = update.location or None  # type: ignore[assignment]
    if update.experience_level is not None:
        if update.experience_level not in _EXPERIENCE_LEVELS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"experience_level must be one of {', '.join(_EXPERIENCE_LEVELS)}"
                ),
            )
        user.experience_level = update.experience_level  # type: ignore[assignment]
    if update.domains is not None:
        user.domains = _normalize_domains(update.domains)  # type: ignore[assignment]
    if update.skills is not None:
        user.skills = [  # type: ignore[assignment]
            str(s).strip() for s in update.skills if str(s).strip()
        ]
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
