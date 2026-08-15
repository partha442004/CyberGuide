"""One-click email action links.

Digest emails embed small signed links (``/api/v1/email/apply``) so members
who never open the dashboard can still record applications straight from the
email — which is what powers the follow-up nudges and the weekly "Your week
in applications" recap for them.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.config import get_settings
from interntrack.database.session import get_db
from interntrack.domain.enums import ApplicationStatus
from interntrack.services.application_service import ApplicationService
from interntrack.services.job_service import JobService
from interntrack.utils.helpers import verify_apply_token

router = APIRouter()


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
