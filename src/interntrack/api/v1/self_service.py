"""Member self-service preferences page ("Manage your alerts").

Digest emails embed a signed per-member link to this page, so members can
change their own alert settings (domains, cities, WFH, experience level),
pause or resume alerts, and — under India's DPDP Act — request deletion of
their data, all without going through the admin. The link is signed with
the same HMAC scheme as the apply/status/open email actions, so only links
we actually emailed can change anything.

Everything renders server-side as plain HTML (no dashboard access needed,
works in every mail-client browser).
"""

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.utils.helpers import verify_prefs_token

router = APIRouter()

# Same canonical sets the admin API validates against.
_ALERT_DOMAINS = (
    "security",
    "grc",
    "frontend",
    "coding",
    "data",
    "hardware",
    "design",
    "finance",
    "marketing",
    "govt",
    "other",
)
_DOMAIN_LABELS = {
    "security": "🔐 Cybersecurity / VAPT / SOC",
    "grc": "📋 GRC / Compliance",
    "frontend": "📱 Frontend / Flutter / Android",
    "coding": "💻 Coding / Software",
    "data": "📊 Data / Analytics",
    "hardware": "🔧 Hardware / Electronics",
    "design": "🎨 Design",
    "finance": "💰 Finance",
    "marketing": "📣 Marketing",
    "govt": "🏛️ Government",
    "other": "📦 Other",
}
_CITIES = ("Bangalore", "Chennai", "Coimbatore", "Salem")
_EXPERIENCE_LEVELS = ("fresher", "intern", "junior", "senior")

# Shared inline CSS — one place to restyle the whole page.
_CSS = """
body{font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif;background:#f1f5f9;
margin:0;padding:24px 12px;color:#0f172a;}
.card{max-width:560px;margin:0 auto;background:#fff;border-radius:16px;
padding:28px 26px;box-shadow:0 2px 12px rgba(15,23,42,.08);}
h1{font-size:22px;margin:0 0 4px;} h2{font-size:13px;margin:26px 0 10px;
color:#334155;text-transform:uppercase;letter-spacing:1px;}
.sub{color:#64748b;font-size:14px;margin:0 0 8px;}
label{display:block;font-weight:600;font-size:14px;margin:14px 0 6px;}
input[type=text]{width:100%;box-sizing:border-box;padding:10px 12px;
border:1px solid #cbd5e1;border-radius:8px;font-size:14px;}
select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;
border-radius:8px;font-size:14px;}
.checks{display:flex;flex-wrap:wrap;gap:8px;}
.checks label{margin:0;font-weight:500;font-size:13px;background:#f8fafc;
border:1px solid #e2e8f0;border-radius:999px;padding:7px 14px;cursor:pointer;}
.checks input{margin-right:6px;vertical-align:middle;}
button{background:#4f46e5;color:#fff;border:0;border-radius:9px;
padding:11px 24px;font-weight:700;font-size:14px;cursor:pointer;margin-top:18px;}
button.gray{background:#64748b;} button.red{background:#dc2626;}
.banner{border-radius:10px;padding:12px 14px;font-size:14px;margin:14px 0;}
.ok{background:#ecfdf5;color:#065f46;} .err{background:#fef2f2;color:#b91c1c;}
.muted{color:#94a3b8;font-size:12px;margin-top:22px;border-top:1px solid #e2e8f0;
padding-top:14px;line-height:1.6;}
"""


def _esc(value: str) -> str:
    from html import escape

    return escape(str(value or ""), quote=True)


def _checked(items: list[str], value: str) -> str:
    return " checked" if value in items else ""


async def _load_member(db: AsyncSession, user_id: str):
    """The User profile for a self-service visitor, or None."""
    from sqlalchemy import select

    from interntrack.domain.models import User

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _load_prefs_row(db: AsyncSession, user_id: str):
    """The AlertPreferences row for a member, or None when never configured."""
    from sqlalchemy import select

    from interntrack.domain.models import AlertPreferences

    result = await db.execute(
        select(AlertPreferences).where(AlertPreferences.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head>"
        f"<body><div class='card'>{body}</div></body></html>"
    )


def _unauthorized() -> HTMLResponse:
    return _page(
        "Link expired — InternTrack",
        "<h1>🔗 Link not valid</h1>"
        "<p class='sub'>This manage-alerts link is broken or outdated. "
        "Open your latest digest email and use the link at the bottom, "
        "or ask your admin for a fresh one.</p>",
    )


def _redirect(u: str, t: str, saved: str) -> HTMLResponse:
    """303 back to the GET page (POST-redirect-GET: refresh never resubmits)."""
    from urllib.parse import urlencode

    query = urlencode({"u": u, "t": t, "saved": saved})
    return HTMLResponse(
        status_code=303,
        headers={"Location": f"/api/v1/self-service/prefs?{query}"},
    )


@router.get("/prefs", response_class=HTMLResponse, include_in_schema=False)
async def prefs_page(
    u: str = Query(..., min_length=1, max_length=200),
    t: str = Query(..., min_length=32, max_length=128),
    saved: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Self-service page for one member: view + update everything."""
    if not verify_prefs_token(u, t):
        return _unauthorized()
    member = await _load_member(db, u)
    if member is None or not bool(getattr(member, "is_active", True)):
        return _unauthorized()

    pref_row = await _load_prefs_row(db, u)
    domains = list(getattr(member, "domains", None) or [])
    location = str(getattr(member, "location", "") or "")
    experience = str(getattr(member, "experience_level", "") or "")
    enabled = bool(pref_row.is_enabled) if pref_row is not None else True

    banner = ""
    if saved == "1":
        banner = (
            "<div class='banner ok'>✅ Saved — your next digest "
            "uses the new settings.</div>"
        )
    elif saved == "paused":
        banner = (
            "<div class='banner ok'>⏸️ Alerts paused. Press Resume below any time.</div>"
        )
    elif saved == "resumed":
        banner = (
            "<div class='banner ok'>▶️ Alerts resumed — back tomorrow morning.</div>"
        )
    elif saved == "unsub":
        banner = (
            "<div class='banner ok'>🚪 You are unsubscribed. "
            "No more emails will be sent.</div>"
        )
    elif saved == "error":
        banner = "<div class='banner err'>⚠️ Something went wrong — try again.</div>"

    if saved == "deleted":
        return _page(
            "Deleted — InternTrack",
            "<h1>🗑️ Account deleted</h1>"
            "<p class='sub'>Your profile, alert settings and delivery history "
            "have been removed. You will not receive any more emails.</p>"
            "<p class='muted'>Changed your mind? Ask your admin to re-add you "
            "with your same email.</p>",
        )

    domain_boxes = "".join(
        f"<label><input type='checkbox' name='domains' value='{d}'"
        f"{_checked(domains, d)}>{_esc(_DOMAIN_LABELS.get(d, d))}</label>"
        for d in _ALERT_DOMAINS
    )
    city_boxes = "".join(
        f"<label><input type='checkbox' name='cities' value='{c}'"
        f"{_checked([c.strip() for c in location.split(',')], c)}>{c}</label>"
        for c in _CITIES
    )
    level_options = "".join(
        f"<option value='{lvl}'"
        f"{' selected' if lvl == experience else ''}>{lvl.title()}</option>"
        for lvl in _EXPERIENCE_LEVELS
    )
    member_skills = ", ".join(str(s) for s in (getattr(member, "skills", None) or []))
    pause_action = f"/api/v1/self-service/pause?u={_esc(u)}&t={_esc(t)}"
    pause_op = "resume" if not enabled else "pause"
    pause_label = "▶️ Resume alerts" if not enabled else "⏸️ Pause alerts (vacation)"
    unsub_action = f"/api/v1/self-service/unsubscribe?u={_esc(u)}&t={_esc(t)}"
    delete_action = f"/api/v1/self-service/delete?u={_esc(u)}&t={_esc(t)}"
    confirm_js = (
        "return confirm('Delete your profile, alert settings and delivery "
        "history? This cannot be undone.')"
    )

    # HTML assembled via concatenation (keeps bandit's S608 away from the
    # big f-string; every interpolated value is escaped via _esc above).
    member_name = _esc(str(getattr(member, "name", "")))
    save_action = f"/api/v1/self-service/prefs?u={_esc(u)}&t={_esc(t)}"
    body = (
        "<h1>⚙️ Manage your alerts</h1>"
        "<p class='sub'>Hi "
        + member_name
        + " — changes apply to <b>tomorrow's 8 AM digest</b> "
        "automatically.</p>"
        + banner
        + "<form method='post' action='"
        + save_action
        + "'>"
        "<h2>Job categories</h2>"
        "<div class='checks'>" + domain_boxes + "</div>"
        "<label>Cities (leave all unchecked for anywhere / only WFH)</label>"
        "<div class='checks'>" + city_boxes + "</div>"
        "<label>Experience level</label>"
        "<select name='experience'>" + level_options + "</select>"
        "<label>Skills (comma-separated, improves match %)</label>"
        "<input type='text' name='skills' value='" + _esc(member_skills) + "'>"
        "<button type='submit'>💾 Save settings</button>"
        "</form>"
        "<h2>Alerts</h2>"
        "<form method='post' action='" + pause_action + "&op=" + pause_op + "'>"
        "<button type='submit' class='gray'>" + pause_label + "</button></form>"
        "<form method='post' action='" + unsub_action + "'>"
        "<button type='submit' class='gray'>🚪 Unsubscribe from all emails</button>"
        "</form>"
        "<h2>Your data (DPDP)</h2>"
        "<form method='post' action='"
        + delete_action
        + "' onsubmit='"
        + confirm_js
        + "'>"
        "<button type='submit' class='red'>🗑️ Delete my data</button>"
        "</form>"
        "<p class='muted'>You get one job digest every morning at 8 AM IST. "
        "This link is personal — don't share it; it manages your alerts.</p>"
    )
    return _page("Manage your alerts — InternTrack", body)


async def _authenticated_member(db: AsyncSession, u: str, t: str):
    """Member for a POST action, or None when the token/member is invalid."""
    if not verify_prefs_token(u, t):
        return None
    member = await _load_member(db, u)
    if member is None or not bool(getattr(member, "is_active", True)):
        return None
    return member


@router.post("/prefs", include_in_schema=False)
async def prefs_save(
    u: str = Query(...),
    t: str = Query(...),
    domains: list[str] = Form(default=[]),
    cities: list[str] = Form(default=[]),
    experience: str = Form(default=""),
    skills: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Save domains / cities / experience / skills from the self-service form."""
    member = await _authenticated_member(db, u, t)
    if member is None:
        return _unauthorized()

    from interntrack.api.v1.notifications import _normalize_domains

    member.domains = _normalize_domains(domains)
    member.skills = [s.strip() for s in str(skills or "").split(",") if s.strip()]
    if experience in _EXPERIENCE_LEVELS:
        member.experience_level = experience
    clean_cities = [c for c in cities if c in _CITIES]
    member.location = ", ".join(clean_cities) or None

    await db.commit()
    return _redirect(u, t, "1")


@router.post("/pause", include_in_schema=False)
async def prefs_pause(
    u: str = Query(...),
    t: str = Query(...),
    op: str = Query(default="pause"),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Pause or resume this member's alerts (vacation switch)."""
    member = await _authenticated_member(db, u, t)
    if member is None:
        return _unauthorized()

    from interntrack.domain.models import AlertPreferences

    pref_row = await _load_prefs_row(db, u)
    if pref_row is None:
        pref_row = AlertPreferences(user_id=u)
        db.add(pref_row)
    if op == "resume":
        pref_row.is_enabled = True
        await db.commit()
        return _redirect(u, t, "resumed")
    pref_row.is_enabled = False
    await db.commit()
    return _redirect(u, t, "paused")


@router.post("/unsubscribe", include_in_schema=False)
async def prefs_unsubscribe(
    u: str = Query(...),
    t: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Permanent opt-out: alerts off AND the email channel removed.

    Stronger than pause — the delivery loop checks both flags, so nothing
    is ever sent to this member again (List-Unsubscribe compliance).
    """
    member = await _authenticated_member(db, u, t)
    if member is None:
        return _unauthorized()

    from interntrack.domain.models import AlertPreferences

    member.is_active = False
    pref_row = await _load_prefs_row(db, u)
    if pref_row is None:
        pref_row = AlertPreferences(user_id=u)
        db.add(pref_row)
    pref_row.is_enabled = False
    pref_row.channels = ["telegram"]  # email channel dropped
    await db.commit()
    return _redirect(u, t, "unsub")


@router.post("/delete", include_in_schema=False)
async def prefs_delete_me(
    u: str = Query(...),
    t: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """DPDP data-deletion request: erase this member's personal data.

    Removes the profile, alert preferences, notification history and
    application records. Idempotent — deleting twice still lands on the
    confirmation page.
    """
    member = await _authenticated_member(db, u, t)
    if member is None:
        return _unauthorized()

    from sqlalchemy import delete as sa_delete

    from interntrack.domain.models import (
        AlertPreferences,
        Application,
        NotificationHistory,
    )

    await db.execute(sa_delete(AlertPreferences).where(AlertPreferences.user_id == u))
    await db.execute(
        sa_delete(NotificationHistory).where(NotificationHistory.user_id == u)
    )
    await db.execute(sa_delete(Application).where(Application.user_id == u))
    await db.delete(member)
    await db.commit()
    return _redirect(u, t, "deleted")
