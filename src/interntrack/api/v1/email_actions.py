"""One-click email action links.

Digest emails embed small signed links (``/api/v1/email/apply``) so members
who never open the dashboard can still record applications straight from the
email — which is what powers the follow-up nudges and the weekly "Your week
in applications" recap for them.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.config import get_settings
from interntrack.database.session import get_db
from interntrack.domain.enums import ApplicationStatus
from interntrack.services.application_service import ApplicationService
from interntrack.services.job_service import JobService
from interntrack.utils.helpers import (
    verify_apply_token,
    verify_open_token,
    verify_status_token,
)

router = APIRouter()

# Statuses the nudge-email buttons can set (member-facing labels).
_STATUS_BUTTONS = {
    "interview": (ApplicationStatus.INTERVIEW, "🗓️ Interview"),
    "rejected": (ApplicationStatus.REJECTED, "❌ Rejected"),
    "offer": (ApplicationStatus.OFFER, "🎉 Offer"),
}

# 1x1 transparent GIF served by the open-tracking pixel.
_TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


@router.get("/apply", include_in_schema=False)
async def email_apply(
    u: str = Query(..., min_length=1, max_length=200),
    j: str = Query(..., min_length=1, max_length=200),
    t: str = Query(..., min_length=32, max_length=128),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Record an application from a digest-email click, then open the job.

    The link is signed (HMAC of user + job with the server secret), so only
    links we actually emailed can create applications. Creating is
    idempotent — clicking twice never duplicates the application, and a
    SAVED application is promoted to APPLIED with ``applied_at`` set (which
    is what the follow-up nudges and weekly recap count).
    """
    if not verify_apply_token(u, j, t):
        raise HTTPException(status_code=400, detail="Invalid or expired apply link")

    service = ApplicationService(db)
    existing = await service.get_application_for_job(j, user_id=u)
    if existing is None:
        created = await service.create_application(j, user_id=u)
        created.source = "email"  # type: ignore[assignment]
        await service.update_status(str(created.id), ApplicationStatus.APPLIED)
    elif existing.status != ApplicationStatus.APPLIED:
        if not getattr(existing, "source", None):
            existing.source = "email"  # type: ignore[assignment]
        await service.update_status(str(existing.id), ApplicationStatus.APPLIED)

    job = await JobService(db).get_job(j)
    if job is not None and job.url:
        return RedirectResponse(str(job.url), status_code=302)
    base = (get_settings().api_base_url or "").strip().rstrip("/")
    return RedirectResponse(base or "/", status_code=302)


@router.get("/open", include_in_schema=False)
async def email_open(
    u: str = Query(..., min_length=1, max_length=200),
    t: str = Query(..., min_length=32, max_length=128),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Record that a member opened a digest email (tracking pixel).

    The digest HTML embeds a 1x1 transparent image pointing here; loading
    it stamps ``opened_at`` on the member's most recent digest send from
    the last 48h. Always answers with the transparent GIF so email
    clients never error, and never raises on DB trouble (a failed pixel
    must not break rendering of the email).
    """
    from datetime import UTC, datetime, timedelta

    if not verify_open_token(u, t):
        raise HTTPException(status_code=400, detail="Invalid or expired open link")

    try:
        from sqlalchemy import select

        from interntrack.domain.models import NotificationHistory

        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48)
        result = await db.execute(
            select(NotificationHistory)
            .where(
                NotificationHistory.user_id == u,
                NotificationHistory.created_at >= since,
            )
            .order_by(NotificationHistory.created_at.desc())
            .limit(1)
        )
        row = result.scalars().first()
        if row is not None and getattr(row, "opened_at", None) is None:
            row.opened_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]
            await db.flush()
    except Exception:  # noqa: BLE001, S110 - the pixel must never error
        pass
    return Response(content=_TRANSPARENT_GIF, media_type="image/gif")


@router.get("/status", include_in_schema=False)
async def email_status(
    u: str = Query(..., min_length=1, max_length=200),
    a: str = Query(..., min_length=1, max_length=200),
    s: str = Query(..., min_length=1, max_length=20),
    t: str = Query(..., min_length=32, max_length=128),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Update an application's status from a nudge-email button link.

    The follow-up nudge email offers signed one-click buttons so members
    who never open the dashboard can record "interview / rejected / offer"
    — which then feeds the interview reminders, the weekly recap and the
    dashboard pipeline. The link is HMAC-bound to the member + application
    + status, and the application must actually belong to the member.
    Responds with a small confirmation page.
    """
    from sqlalchemy import select

    from interntrack.domain.models import Application

    entry = _STATUS_BUTTONS.get(s)
    if entry is None or not verify_status_token(u, a, s, t):
        raise HTTPException(status_code=400, detail="Invalid or expired status link")
    new_status, label = entry

    result = await db.execute(select(Application).where(Application.id == a))
    app = result.scalars().first()
    if app is None or str(getattr(app, "user_id", "") or "") != u:
        raise HTTPException(status_code=404, detail="Application not found")

    service = ApplicationService(db)
    await service.update_status(str(app.id), new_status)

    html = (
        "<html><body style='font-family:Inter,Arial,sans-serif;"
        "text-align:center;padding:48px 16px;'>"
        "<div style='max-width:420px;margin:0 auto;'>"
        "<div style='font-size:40px;'>✅</div>"
        "<h2 style='margin:8px 0;'>Status updated</h2>"
        f"<p style='color:#475569;'>Marked as <b>{label}</b>. Your next "
        "digest and the weekly recap will reflect it.</p>"
        "<p style='color:#94a3b8;font-size:13px;'>Need to change it? "
        "Ask your admin.</p>"
        "</div></body></html>"
    )
    return Response(content=html, media_type="text/html")
