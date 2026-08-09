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
from sqlalchemy import delete, select
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
    if settings.is_twilio_configured:
        channels.append("sms")
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


async def _send_welcome(user: User, db: AsyncSession) -> None:
    """Send a welcome message to a brand-new account (best-effort).

    Uses the same HTML-friendly text for email and Telegram. Never raises:
    a welcome that can't be delivered must not block or fail registration.
    """
    try:
        from interntrack.services.notification_service import NotificationManager

        channels = _configured_channels()
        if not channels:
            return
        manager = NotificationManager(db)
        name = _esc_html(str(user.name or "there"))
        domains = list(user.domains or [])
        domains_txt = ", ".join(_esc_html(d) for d in domains)
        message = (
            f"<b>Hey {name} 👋</b><br/><br/>"
            "Your account is ready and your <b>personalized job alerts are ON</b>.<br/>"
            "Every day at 8:00 / 13:00 / 19:00 IST we'll send jobs"
            + (f" in <b>{domains_txt}</b>" if domains_txt else "")
            + " to this inbox"
            + (" and your Telegram" if user.telegram_chat_id else "")
            + ".<br/><br/>"
            "Upload your resume for match %, track applications, and invite "
            "friends from the dashboard.<br/>Good luck! 🚀"
        )
        await manager.notify(
            channels,
            message,
            subject="🎉 Welcome to InternTrack!",
            recipient={
                "email": user.email,
                "telegram_chat_id": user.telegram_chat_id,
            },
        )
    except Exception:  # noqa: BLE001 - best-effort onboarding message
        return


def _esc_html(value: str) -> str:
    """Escape untrusted text before embedding in an HTML message."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        phone_number=payload.phone_number or None,
        location=payload.location or None,
        experience_level=experience or None,
        domains=_normalize_domains(payload.domains),
        skills=[str(s).strip() for s in payload.skills if str(s).strip()],
        is_active=True,
        access_token=_new_access_token(),
        referred_by=payload.referred_by or None,
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
    # Best-effort welcome message (email + Telegram) — never blocks signup.
    await _send_welcome(user, db)
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


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete an account and all of its data.

    Removes the profile plus every user-scoped row: alert preferences,
    notification history, applications (+ their status history), company
    watchlists, user skills, and the resume records in the shared
    ``resume_data`` / ``resume_match_results`` tables (when present). Returns
    404 for an unknown user id.
    """
    from sqlalchemy import text

    from interntrack.domain.models import (
        Application,
        ApplicationStatusHistory,
        CompanyWatchlist,
        NotificationHistory,
        UserSkill,
    )

    user = await _get_user_or_404(db, user_id)

    # Cross-module resume rows live in the shared database under cybershield's
    # ``resume_data`` table. Best-effort cleanup runs FIRST because the table
    # only exists on the live Postgres (not in a fresh interntrack-only test
    # database); a failed probe is rolled back before the real deletes below
    # so it can never undo them.
    try:
        await db.execute(
            text(
                "DELETE FROM resume_match_results "
                "WHERE resume_id IN (SELECT id FROM resume_data "
                "WHERE user_id = :uid)"
            ),
            {"uid": user_id},
        )
        await db.execute(
            text("DELETE FROM resume_data WHERE user_id = :uid"),
            {"uid": user_id},
        )
    except Exception:  # noqa: BLE001 - best-effort cross-module cleanup
        await db.rollback()

    # Applications first — their status-history rows reference application ids.
    app_ids = list(
        (await db.execute(select(Application.id).where(Application.user_id == user_id)))
        .scalars()
        .all()
    )
    if app_ids:
        await db.execute(
            delete(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id.in_(app_ids)
            )
        )
    await db.execute(delete(Application).where(Application.user_id == user_id))
    await db.execute(
        delete(CompanyWatchlist).where(CompanyWatchlist.user_id == user_id)
    )
    await db.execute(delete(UserSkill).where(UserSkill.user_id == user_id))
    await db.execute(
        delete(AlertPreferences).where(AlertPreferences.user_id == user_id)
    )
    await db.execute(
        delete(NotificationHistory).where(NotificationHistory.user_id == user_id)
    )

    await db.delete(user)
    await db.commit()


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
    if update.phone_number is not None:
        user.phone_number = update.phone_number or None  # type: ignore[assignment]
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
