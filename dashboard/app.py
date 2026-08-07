"""
InternTrack Dashboard - Streamlit Application
"""

import os
from contextlib import suppress
from datetime import UTC, datetime, timedelta, timezone
from html import escape
from typing import Any

import httpx
import plotly.express as px
import streamlit as st

# Page config
st.set_page_config(
    page_title="InternTrack Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design system (professional theme, adapts to light/dark)
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
    /* ---------- Base typography ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [data-testid="stAppViewContainer"], .stMarkdown, .stCaption {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* ---------- Theme variables ---------- */
    html[data-theme="light"] {
        --bg: #f8fafc;
        --card: #ffffff;
        --border: #e2e8f0;
        --text: #0f172a;
        --muted: #64748b;
        --soft: rgba(15, 23, 42, 0.045);
    }
    html[data-theme="dark"] {
        --bg: #0b1120;
        --card: #111a2e;
        --border: #1e2a44;
        --text: #e2e8f0;
        --muted: #94a3b8;
        --soft: rgba(148, 163, 184, 0.08);
    }

    /* ---------- App background ---------- */
    [data-testid="stAppViewContainer"] {
        background: var(--bg);
    }
    [data-testid="stHeader"] {
        background: transparent;
    }

    /* ---------- Metric cards ---------- */
    .metric-card {
        border-radius: 16px;
        padding: 20px 22px;
        color: #ffffff;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 96px;
        transition: transform .18s ease, box-shadow .18s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 14px 32px rgba(0, 0, 0, 0.24);
    }
    .metric-icon {
        font-size: 2.1em;
        line-height: 1;
        background: rgba(255, 255, 255, 0.22);
        border-radius: 12px;
        padding: 10px 12px;
    }
    .metric-value {
        font-size: 1.9em;
        font-weight: 800;
        line-height: 1.1;
    }
    .metric-label {
        font-size: 0.82em;
        opacity: 0.9;
        font-weight: 500;
        letter-spacing: .02em;
    }

    /* ---------- Stat tiles (Saved Jobs summary) ---------- */
    .stat-tile {
        border: 1px solid var(--border);
        background: var(--card);
        border-radius: 14px;
        padding: 14px 18px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    .stat-value {
        font-size: 1.7em;
        font-weight: 800;
        color: var(--text);
        line-height: 1.2;
    }
    .stat-label {
        font-size: 0.78em;
        color: var(--muted);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: .05em;
    }

    /* ---------- Category section headers ---------- */
    .cat-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 26px 0 4px;
        padding: 13px 18px;
        border-radius: 14px;
        background: var(--soft);
        border-left: 5px solid #64748b;
    }
    .cat-icon {
        font-size: 1.15em;
        border-radius: 10px;
        padding: 7px 9px;
        color: #fff;
        box-shadow: 0 3px 8px rgba(0, 0, 0, 0.18);
    }
    .cat-name {
        font-size: 1.06em;
        font-weight: 700;
        color: var(--text);
        flex: 1;
    }
    .cat-badge {
        color: #fff;
        font-weight: 700;
        font-size: 0.82em;
        border-radius: 999px;
        padding: 3px 12px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.18);
    }
    .cat-pct {
        font-size: 0.78em;
        color: var(--muted);
        font-weight: 600;
    }
    .cat-bar {
        height: 5px;
        border-radius: 999px;
        background: var(--soft);
        margin: 0 18px 10px 18px;
        overflow: hidden;
    }
    .cat-bar-fill {
        height: 100%;
        border-radius: 999px;
        transition: width .6s ease;
    }

    /* ---------- Job cards ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 14px !important;
        border: 1px solid var(--border) !important;
        background: var(--card);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
        transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover > div {
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.14);
        transform: translateY(-2px);
        border-color: #667eea !important;
    }

    /* ---------- Chips ---------- */
    .chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 8px 0 10px;
    }
    .chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 0.78em;
        font-weight: 600;
        color: var(--text);
        background: var(--soft);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 4px 11px;
    }
    .chip-salary {
        color: #059669;
        background: rgba(16, 185, 129, 0.10);
        border-color: rgba(16, 185, 129, 0.25);
    }
    html[data-theme="dark"] .chip-salary { color: #34d399; }

    /* ---------- Job title ---------- */
    .job-title {
        font-size: 1.12em;
        font-weight: 700;
        color: var(--text);
        margin: 0;
    }
    .job-desc {
        color: var(--muted);
        font-size: 0.9em;
        line-height: 1.55;
        margin-top: 6px;
    }

    /* ---------- Pills / buttons polish ---------- */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
    div[data-testid="stPills"] button {
        border-radius: 999px !important;
        font-weight: 600;
    }
    div[data-testid="stPills"] button[aria-pressed="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-color: transparent !important;
        color: #fff !important;
    }

    /* ---------- Section subtitles ---------- */
    .section-title {
        font-size: 1.25em;
        font-weight: 800;
        color: var(--text);
        margin: 22px 0 8px;
    }
    .section-sub {
        color: var(--muted);
        font-size: 0.9em;
        margin-bottom: 14px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _get_setting(name: str, default: str) -> str:
    """Resolve a config value: st.secrets first, then env var, then default."""
    with suppress(Exception):
        secrets = getattr(st, "secrets", {})
        if name in secrets:
            return secrets[name]
    return os.environ.get(name, default)


# Base URLs for the InternTrack API.
API_URL = _get_setting("API_URL", "https://cyberguide-api.vercel.app/api/v1")
HEALTH_URL = _get_setting("HEALTH_URL", "https://cyberguide-api.vercel.app/health")
DEFAULT_VERSION = "1.20.0"


# ---------------------------------------------------------------------------
# Domain classification (mirrors the API's report classifier)
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "security",
        (
            "security",
            "cyber",
            "soc",
            "pentest",
            "vapt",
            "infosec",
            "appsec",
            "devsecops",
            "siem",
            "malware",
            "threat",
            "vulnerab",
            "incident response",
            "red team",
            "blue team",
            "ethical hack",
            "information security",
        ),
    ),
    (
        "coding",
        (
            "software",
            "developer",
            "engineer",
            "programmer",
            "backend",
            "frontend",
            "full stack",
            "fullstack",
            "devops",
            "sre",
            "python",
            "javascript",
            "typescript",
            "java",
            "react",
            "node",
            "sql",
            "data engineer",
            "machine learning",
            "data scientist",
            "ai",
            "architect",
        ),
    ),
    (
        "data",
        ("data", "analyst", "analytics", "business intelligence", "database"),
    ),
    ("design", ("designer", "ux", "graphic", "visual", "product design")),
    ("finance", ("finance", "accountant", "accounting", "audit", "tax", "bookkeep")),
    (
        "marketing",
        (
            "marketing",
            "sales",
            "account",
            "growth",
            "content",
            "social media",
            "brand",
            "seo",
            "customer success",
            "business development",
        ),
    ),
]

_DOMAIN_LABELS = {
    "security": "🔐 Cybersecurity / VAPT / SOC",
    "coding": "💻 Coding / Software",
    "data": "📊 Data & Analytics",
    "design": "🎨 Design",
    "finance": "💰 Finance / Admin",
    "marketing": "📣 Marketing / Sales",
    "other": "📦 Other",
}

_DOMAIN_ORDER = [
    "security",
    "coding",
    "data",
    "design",
    "finance",
    "marketing",
    "other",
]

# Accent styles per category (color = badge/bar accent, grad = icon tile,
# icon = emoji shown inside the tile). Keys mirror _DOMAIN_LABELS.
_CATEGORY_STYLE = {
    "security": {
        "color": "#e5484d",
        "grad": "linear-gradient(135deg,#ff6b6b,#c0392b)",
        "icon": "🔐",
    },
    "coding": {
        "color": "#3b82f6",
        "grad": "linear-gradient(135deg,#60a5fa,#1d4ed8)",
        "icon": "💻",
    },
    "data": {
        "color": "#8b5cf6",
        "grad": "linear-gradient(135deg,#a78bfa,#6d28d9)",
        "icon": "📊",
    },
    "design": {
        "color": "#ec4899",
        "grad": "linear-gradient(135deg,#f472b6,#be185d)",
        "icon": "🎨",
    },
    "finance": {
        "color": "#10b981",
        "grad": "linear-gradient(135deg,#34d399,#047857)",
        "icon": "💰",
    },
    "marketing": {
        "color": "#f59e0b",
        "grad": "linear-gradient(135deg,#fbbf24,#b45309)",
        "icon": "📣",
    },
    "other": {
        "color": "#64748b",
        "grad": "linear-gradient(135deg,#94a3b8,#475569)",
        "icon": "📦",
    },
}


def classify_domain(title: str) -> str:
    """Classify a job title into a domain bucket (mirrors the API)."""
    raw = f"{title or ''}"
    # RSS titles prefix the company: "Acme Corp: Security Engineer".
    role = raw.split(": ", 1)[-1] if ": " in raw else raw
    text = role.lower()
    for domain, keywords in _DOMAIN_KEYWORDS:
        if any(k in text for k in keywords):
            return domain
    return "other"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _api_raw(
    endpoint: str,
    method: str = "GET",
    json_data: dict | None = None,
    files: Any = None,
    timeout: int = 30,
) -> Any:
    """API caller returning the raw response (to inspect status codes).

    Unlike ``_api`` (which only returns JSON on 200), this returns the full
    httpx response so callers can distinguish 201, 404 and 409, or None when
    the API is unreachable.
    """
    url = f"{API_URL}{endpoint}"
    with suppress(Exception):
        if method == "POST":
            if files:
                return httpx.post(url, files=files, timeout=timeout)
            return httpx.post(url, json=json_data or {}, timeout=timeout)
        if method == "PUT":
            return httpx.put(url, json=json_data or {}, timeout=timeout)
        if method == "PATCH":
            return httpx.patch(url, json=json_data or {}, timeout=timeout)
        return httpx.get(url, timeout=timeout)
    return None


def _api(
    endpoint: str,
    method: str = "GET",
    json_data: dict | None = None,
    files: Any = None,
    timeout: int = 30,
) -> Any:
    """Generic API caller — returns parsed JSON on 200, else None."""
    resp = _api_raw(
        endpoint, method=method, json_data=json_data, files=files, timeout=timeout
    )
    if resp is not None and resp.status_code == 200:
        with suppress(Exception):
            return resp.json()
    return None


def fetch_data(endpoint: str) -> Any:
    """GET from the API — returns None when unreachable."""
    return _api(endpoint, method="GET")


@st.cache_data(ttl=60, show_spinner=False)
def fetch_version() -> str:
    """Fetch the live API version from /health (cached 60s)."""
    with suppress(Exception):
        resp = httpx.get(HEALTH_URL, timeout=5)
        if resp.status_code == 200:
            version = resp.json().get("version")
            if version:
                return version
    return DEFAULT_VERSION


def _time_ago(iso_str: Any) -> str:
    """Human-friendly relative time from an ISO timestamp."""
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - dt
    except (ValueError, TypeError):
        return "Unknown"
    secs = delta.total_seconds()
    if secs < 0:
        return "Just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    days = int(secs // 86400)
    if days == 1:
        return "Yesterday"
    if days < 30:
        return f"{days}d ago"
    return str(iso_str)[:10]


def _is_fresh_24h(iso_str: Any) -> bool:
    """True when the timestamp is within the last 24 hours."""
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (datetime.now(UTC) - dt).total_seconds() < 86400
    except (ValueError, TypeError):
        return False


# India / Kolkata is UTC+5:30 with no DST — a fixed offset avoids needing the
# IANA tz database (tzdata) which is not bundled with Windows Python.
_IST = timezone(timedelta(hours=5, minutes=30))


def _ist_time(iso_str: Any) -> str:
    """Convert an ISO UTC timestamp to India/Kolkata local time."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(_IST).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(iso_str)[:16]


# ---------------------------------------------------------------------------
# UI building blocks
# ---------------------------------------------------------------------------


def _metric_card(icon: str, value: Any, label: str, grad: str) -> None:
    """Gradient metric tile for the Overview page."""
    st.markdown(
        f'<div class="metric-card" style="background:{grad}">'
        f'<span class="metric-icon">{icon}</span>'
        f'<div><div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div></div></div>',
        unsafe_allow_html=True,
    )


def _stat_tile(value: Any, label: str) -> None:
    """Compact stat tile for the Saved Jobs summary row."""
    st.markdown(
        f'<div class="stat-tile"><div class="stat-value">{value}</div>'
        f'<div class="stat-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


def _category_header(domain: str, count: int, total: int) -> None:
    """Styled category section header with badge + share progress bar."""
    style = _CATEGORY_STYLE.get(domain, _CATEGORY_STYLE["other"])
    pct = (count / total * 100) if total else 0
    st.markdown(
        f'<div class="cat-header" style="border-left-color:{style["color"]}">'
        f'<span class="cat-icon" style="background:{style["grad"]}">'
        f"{style.get('icon', '📌')}</span>"
        f'<span class="cat-name">{_DOMAIN_LABELS.get(domain, domain)}</span>'
        f'<span class="cat-badge" style="background:{style["color"]}">{count}</span>'
        f'<span class="cat-pct">{pct:.0f}% of jobs</span></div>'
        f'<div class="cat-bar"><div class="cat-bar-fill" '
        f'style="width:{pct:.1f}%;background:{style["color"]}"></div></div>',
        unsafe_allow_html=True,
    )


def _render_job(job: dict, match_score: Any = None) -> None:
    """One job as a clean, hoverable card with real widgets.

    All scraped fields (title, company, location, description, ...) are
    untrusted external content, so every value interpolated into HTML is
    escaped before rendering with ``unsafe_allow_html``. When
    ``match_score`` is given (from the Resume Match run), a colored
    match chip is shown on the card.
    """
    title = escape(str(job.get("title", "Untitled")))
    company = escape(str(job.get("company", "Unknown")))
    posted = job.get("posted_at")

    with st.container(border=True):
        col_l, col_r = st.columns([4, 1])

        with col_l:
            st.markdown(f'<div class="job-title">{title}</div>', unsafe_allow_html=True)

            if match_score is not None:
                score = float(match_score)
                if score >= 70:
                    chip_color, icon = "#059669", "🟢"
                elif score >= 40:
                    chip_color, icon = "#d97706", "🟡"
                else:
                    chip_color, icon = "#dc2626", "🔴"
                st.markdown(
                    f'<div class="chip-row"><span class="chip" '
                    f'style="color:{chip_color};background:rgba(5,150,105,0.08);'
                    f'border-color:rgba(5,150,105,0.25);font-weight:700;">'
                    f"{icon} Match: {score:.0f}%</span></div>",
                    unsafe_allow_html=True,
                )

            chips = []
            if job.get("company") and str(job.get("company")) != "Unknown":
                chips.append(f"🏢 {company}")
            if job.get("location"):
                chips.append(f"📍 {escape(str(job.get('location')))}")
            if job.get("source"):
                chips.append(f"🗂 {escape(str(job.get('source')))}")
            if chips:
                st.markdown(
                    '<div class="chip-row">'
                    + "".join(f'<span class="chip">{c}</span>' for c in chips)
                    + "</div>",
                    unsafe_allow_html=True,
                )

            sal_min, sal_max = job.get("salary_min"), job.get("salary_max")
            if sal_min or sal_max:
                sal_a = escape(str(sal_min or "N/A"))
                sal_b = escape(str(sal_max or "N/A"))
                st.markdown(
                    f'<div class="chip-row"><span class="chip chip-salary">💰 '
                    f"{sal_a} – {sal_b}</span></div>",
                    unsafe_allow_html=True,
                )

            if job.get("description"):
                desc = str(job["description"]).strip()
                if desc:
                    st.markdown(
                        f'<div class="job-desc">{escape(desc[:300])}'
                        f"{'…' if len(desc) > 300 else ''}</div>",
                        unsafe_allow_html=True,
                    )

            st.caption(f"🕒 Posted {_time_ago(posted)}")

        with col_r:
            if job.get("url"):
                st.link_button("🔗 View", job["url"], use_container_width=True)
            if st.button(
                "📋 Apply",
                key=f"apply_{job.get('id', title)}",
                use_container_width=True,
            ):
                _track_application(job.get("id"), title)


def _category_picker(options: list[str], labels: dict[str, str]) -> str:
    """Segmented category filter (pills with a radio fallback)."""
    picker = getattr(st, "pills", None)
    if picker is not None:
        try:
            selected = picker(
                "Filter by category",
                options,
                selection_mode="single",
                default="All",
                format_func=lambda d: labels.get(d, d),
            )
            return selected or "All"
        except TypeError:
            pass
    return st.radio(
        "Filter by category",
        options,
        horizontal=True,
        format_func=lambda d: labels.get(d, d),
    )


def _category_picker_multi(label: str, default: list[str]) -> list[str]:
    """Multi-select category pills (with a multiselect fallback).

    Returns the selected keys; callers translate an ``"all"`` selection into
    an empty list (= every category).
    """
    domain_labels = {"all": "All categories"}
    for d in _DOMAIN_ORDER:
        domain_labels[d] = _DOMAIN_LABELS.get(d, d)
    picker = getattr(st, "pills", None)
    if picker is not None:
        try:
            return list(
                picker(
                    label,
                    list(domain_labels.keys()),
                    selection_mode="multi",
                    default=default,
                    format_func=lambda d: domain_labels.get(d, d),
                )
                or []
            )
        except TypeError:
            pass
    return list(
        st.multiselect(
            label,
            list(domain_labels.keys()),
            default=default,
            format_func=lambda d: domain_labels.get(d, d),
        )
        or []
    )


# ---------------------------------------------------------------------------
# User session helpers (multi-user support)
# ---------------------------------------------------------------------------


def _current_user() -> dict | None:
    """The logged-in user profile from the session, or None."""
    user = st.session_state.get("user")
    return user if isinstance(user, dict) and user.get("id") else None


def _current_user_id() -> str:
    """The active user's id — the logged-in account or the legacy default."""
    user = _current_user()
    return user["id"] if user else "user1"


def _track_application(job_id: Any, title: str) -> None:
    """Create an application for the current user via the real API."""
    user_id = _current_user_id()
    resp = _api_raw(
        "/applications/",
        method="POST",
        json_data={"job_id": str(job_id), "user_id": user_id},
        timeout=20,
    )
    if resp is not None and resp.status_code in (200, 201):
        st.success(
            f"✅ Application tracked for **{title}**! Update its status on the "
            "Applications page."
        )
    elif resp is not None and resp.status_code == 422:
        st.error("Couldn't track the application — the job may not be saved yet.")
    else:
        st.error("Applications API unreachable. Is the API server running?")


def _update_application_status(app_id: str, status: str) -> None:
    """Persist an application status change via the real API."""
    resp = _api_raw(
        f"/applications/{app_id}/status",
        method="PATCH",
        json_data={"status": status},
        timeout=20,
    )
    if resp is not None and resp.status_code == 200:
        st.success(f"✅ Status updated to **{status}**")
    else:
        st.error("Could not update status — is the API server running?")


def _login_user(profile: dict) -> None:
    """Store a user profile in the Streamlit session."""
    st.session_state["user"] = profile


def _logout_user() -> None:
    """Clear the logged-in user from the session."""
    st.session_state.pop("user", None)


def show_account() -> None:
    """Register / login page (email-based accounts, no passwords)."""
    st.header("👤 My Account")
    user = _current_user()

    if user:
        # ── Logged in: profile summary ────────────────────────────────
        st.success(f"Signed in as **{user.get('name', '')}**")
        st.markdown(
            "<div class='metric-card' style='background: linear-gradient("
            "135deg,#667eea 0%,#764ba2 100%); padding: 20px; border-radius: "
            "12px; color: white;'>"
            f"<div style='font-size: 1.4em; font-weight: 700;'>{escape(user.get('name', ''))}</div>"
            f"<div style='opacity: 0.85;'>{escape(user.get('email', ''))}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📍 Location", user.get("location") or "—")
        with col2:
            st.metric("🚀 Experience", user.get("experience_level") or "—")
        with col3:
            chat = user.get("telegram_chat_id")
            st.metric("✈️ Telegram", f"✅ {chat}" if chat else "—")

        st.subheader("🏷 Preferred categories")
        domains = user.get("domains") or []
        if domains:
            st.write(" · ".join(_DOMAIN_LABELS.get(d, d) for d in domains))
        else:
            st.caption("All categories")

        st.subheader("🧰 Skills")
        skills = user.get("skills") or []
        if skills:
            st.write(", ".join(skills))
        else:
            st.caption("No skills saved yet — upload your resume to extract them.")

        if st.button("🚪 Log out", use_container_width=True):
            _logout_user()
            st.rerun()
        return

    # ── Not signed in: register or log in ─────────────────────────────
    st.markdown(
        "Create a free account to get **personalized job alerts** — your own "
        "categories, your own resume match %, and delivery to *your* email / "
        "Telegram. Login is by email only (no password)."
    )
    tab_register, tab_login = st.tabs(["✨ Create account", "🔑 Log in"])

    with tab_register:
        with st.form("register_form"):
            name = st.text_input("Full name *")
            email = st.text_input("Email *")
            location = st.text_input("Location", placeholder="e.g. Bengaluru, India")
            experience = st.selectbox(
                "Experience level",
                ["", "fresher", "intern", "junior", "senior"],
                format_func=lambda v: {
                    "": "Select...",
                    "fresher": "🎓 Fresher",
                    "intern": "🧪 Intern",
                    "junior": "🚀 Junior",
                    "senior": "💼 Senior",
                }.get(v, v),
            )
            telegram_chat_id = st.text_input(
                "Telegram chat ID (optional)",
                help="Message @userinfobot on Telegram to see your chat ID — "
                "alerts then reach *your* Telegram instead of the shared chat.",
            )
            domains = _category_picker_multi("🏷 Preferred categories", ["security"])
            skills = st.text_input(
                "Skills (comma-separated)",
                placeholder="e.g. python, burp suite, nmap, linux",
            )
            resume_file = st.file_uploader(
                "Upload your resume (PDF) — optional at signup",
                type=["pdf"],
            )
            submitted = st.form_submit_button("🚀 Create my account", type="primary")

        if submitted:
            if not name.strip() or "@" not in email:
                st.error("Please fill in your name and a valid email.")
                return
            payload = {
                "name": name.strip(),
                "email": email.strip(),
                "location": location.strip() or None,
                "experience_level": experience or None,
                "telegram_chat_id": telegram_chat_id.strip() or None,
                "domains": [] if "all" in domains else domains,
                "skills": [s.strip() for s in skills.split(",") if s.strip()],
            }
            resp = _api_raw(
                "/users/register", method="POST", json_data=payload, timeout=30
            )
            if resp is None:
                st.error("Could not reach the API — is it running?")
                return
            if resp.status_code in (200, 201):
                profile = resp.json()
                _login_user(profile)
                if resume_file is not None:
                    files = {
                        "file": (
                            resume_file.name,
                            resume_file.getvalue(),
                            "application/pdf",
                        )
                    }
                    upload = _api(
                        f"/resumes/upload?user_id={profile['id']}",
                        method="POST",
                        files=files,
                        timeout=30,
                    )
                    if upload:
                        st.success(
                            f"✅ Account created and resume parsed — "
                            f"{len(upload.get('skills', []))} skills extracted!"
                        )
                    else:
                        st.warning(
                            "Account created, but resume parsing failed — "
                            "re-upload it from the Resume Match page."
                        )
                else:
                    st.success(
                        "✅ Account created! Your personalized daily alerts are on."
                    )
                st.rerun()
            else:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                st.error(f"Registration failed: {detail}")

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Your email")
            submitted = st.form_submit_button("🔑 Log in", type="primary")
        if submitted:
            if "@" not in email:
                st.error("Please enter your email.")
                return
            resp = _api_raw(
                "/users/login",
                method="POST",
                json_data={"email": email.strip()},
                timeout=30,
            )
            if resp is None:
                st.error("Could not reach the API — is it running?")
            elif resp.status_code == 200:
                _login_user(resp.json())
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("No account found with this email — create one first.")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main() -> None:
    """Main dashboard function."""
    st.title("📊 InternTrack Dashboard")
    st.markdown("Your internship and job tracking command center")

    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to",
            [
                "Overview",
                "Jobs",
                "Applications",
                "Watchlist",
                "Salary Insights",
                "Weekly Digest",
                "Bookmarks",
                "Expired Jobs",
                "Analytics",
                "Resume Match",
                "Learning",
                "Settings",
                "My Account",
            ],
        )
        st.divider()
        user = _current_user()
        if user:
            st.markdown(f"👤 **{user.get('name', '')}**")
            st.caption(f"Signed in · {user.get('email', '')}")
        else:
            st.caption("Not signed in — browsing as **user1**")

    pages = {
        "Overview": show_overview,
        "Jobs": show_jobs,
        "Applications": show_applications,
        "Watchlist": show_watchlist,
        "Salary Insights": show_salary_insights,
        "Weekly Digest": show_weekly_digest,
        "Bookmarks": show_bookmarks,
        "Expired Jobs": show_expired,
        "Analytics": show_analytics,
        "Resume Match": show_resume_match,
        "Learning": show_learning,
        "Settings": show_settings,
        "My Account": show_account,
    }
    pages.get(page, show_overview)()


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------


def show_overview() -> None:
    """Show overview page."""
    st.header("📈 Overview")

    overview = fetch_data("/dashboard/overview")

    if overview:
        jobs = overview.get("jobs", {})
        apps = overview.get("applications", {})

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            _metric_card(
                "💼",
                jobs.get("total_jobs", 0),
                "Total Jobs",
                "linear-gradient(135deg,#667eea 0%,#764ba2 100%)",
            )
        with col2:
            _metric_card(
                "📝",
                apps.get("total_applications", 0),
                "Applications",
                "linear-gradient(135deg,#f093fb 0%,#f5576c 100%)",
            )
        with col3:
            _metric_card(
                "🎯",
                f"{apps.get('response_rate', 0)}%",
                "Response Rate",
                "linear-gradient(135deg,#4facfe 0%,#00f2fe 100%)",
            )
        with col4:
            _metric_card(
                "🕒",
                apps.get("recent_applications", 0),
                "Recent (7d)",
                "linear-gradient(135deg,#43e97b 0%,#38f9d7 100%)",
            )

        st.markdown("")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Job Types")
            job_types = jobs.get("job_types", [])
            if job_types:
                fig = px.pie(job_types, values="count", names="type", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Application Status")
            status_counts = apps.get("status_counts", {})
            if status_counts:
                fig = px.bar(
                    x=list(status_counts.keys()),
                    y=list(status_counts.values()),
                    labels={"x": "Status", "y": "Count"},
                )
                st.plotly_chart(fig, use_container_width=True)

        st.subheader("🏢 Top Companies")
        top_companies = jobs.get("top_companies", [])
        if top_companies:
            import pandas as pd

            st.dataframe(pd.DataFrame(top_companies), use_container_width=True)
    else:
        st.info("No data available. Start the API server and run job discovery.")


# ---------------------------------------------------------------------------
# Page: Jobs
# ---------------------------------------------------------------------------


def show_jobs() -> None:
    """Show jobs page with working discovery & search."""
    st.header("💼 Jobs")

    tab1, tab2, tab3 = st.tabs(["🔍 Discovery", "📋 Saved Jobs", "🔗 Share a Job"])

    # ------ Tab 1: Discovery ------
    with tab1:
        st.markdown(
            '<div class="section-title">Run Job Discovery</div>'
            '<div class="section-sub">Scrapes job boards for new listings matching '
            "your query.</div>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input(
                "Search query",
                "software engineering internship",
                label_visibility="collapsed",
            )
        with col2:
            run_btn = st.button("🚀 Run Discovery", use_container_width=True)

        if run_btn:
            with st.spinner(f"Scraping job boards for '{query}'..."):
                result = _api(
                    "/jobs/discovery/run",
                    method="POST",
                    json_data={"query": query},
                    timeout=60,
                )
                if result:
                    found = result.get("discovered", 0)
                    saved = result.get("saved", 0)
                    if found > 0:
                        st.success(f"✅ Found **{found}** jobs, saved **{saved}** new!")
                        # Show the discovered jobs with full details
                        jobs = result.get("jobs", [])
                        if jobs:
                            st.subheader(f"🔍 Discovered Jobs ({len(jobs)})")
                            for job in jobs[:20]:  # Show up to 20 jobs
                                title = job.get("title", "Untitled")
                                company = job.get("company", "Unknown")
                                location = job.get("location", "Remote")
                                url = job.get("url", "")
                                source = job.get("source", "")
                                urgency = job.get("urgency", {})
                                urgency_label = urgency.get("label", "")
                                urgency_color = urgency.get("color", "#94a3b8")

                                with st.container():
                                    col1, col2, col3 = st.columns([4, 2, 1])
                                    with col1:
                                        st.markdown(f"**{title}**")
                                        st.caption(f"🏢 {company} · 📍 {location}")
                                    with col2:
                                        if source:
                                            st.caption(f"📡 {source}")
                                        if urgency_label:
                                            st.markdown(
                                                f"<span style='color:{urgency_color};font-size:12px;'>"
                                                f"● {urgency_label}</span>",
                                                unsafe_allow_html=True,
                                            )
                                    with col3:
                                        if url:
                                            st.link_button(
                                                "Apply", url, use_container_width=True
                                            )
                                    st.divider()
                    else:
                        st.info("No new jobs found this time. Try a different query.")
                else:
                    st.error("Discovery API unreachable. Is the API server running?")

        st.divider()
        st.caption(
            "💡 Tip: Try queries like *python developer*, *data science intern*, *cybersecurity*"
        )

    # ------ Tab 2: Saved Jobs (grouped by category) ------
    with tab2:
        jobs_data = fetch_data("/jobs/?limit=100")
        if not jobs_data or not jobs_data.get("jobs"):
            st.info("No jobs saved yet. Run discovery from the Discovery tab!")
        else:
            _render_saved_jobs_tab(jobs_data["jobs"])

    # ------ Tab 3: Share a Job (paste any link) ------
    with tab3:
        _share_job_form()


def _render_saved_jobs_tab(jobs: list) -> None:
    """Render the Saved Jobs tab: category stats, filter pills and sections."""
    # Group jobs by domain category.
    grouped: dict[str, list] = {}
    for job in jobs:
        domain = classify_domain(job.get("title", ""))
        grouped.setdefault(domain, []).append(job)

    fresh_count = sum(1 for j in jobs if _is_fresh_24h(j.get("posted_at")))
    domains_present = [d for d in _DOMAIN_ORDER if d in grouped]

    # Summary stat row.
    stat_cols = st.columns(4)
    with stat_cols[0]:
        _stat_tile(len(jobs), "Saved Jobs")
    with stat_cols[1]:
        _stat_tile(len(domains_present), "Categories")
    with stat_cols[2]:
        _stat_tile(fresh_count, "New · 24h")
    with stat_cols[3]:
        _stat_tile(
            sum(len(grouped[d]) for d in ("security", "coding", "data")),
            "Tech Roles",
        )
    st.markdown("")

    # Location filter (text) — narrows to jobs matching a city/region.
    filter_col1, filter_col2 = st.columns([2, 3])
    with filter_col1:
        location_query = st.text_input(
            "📍 Location filter",
            placeholder="e.g. Bangalore, Remote",
            label_visibility="collapsed",
        )
    with filter_col2:
        st.caption(
            "Filter by city/region — e.g. *Bangalore*, *Bengaluru*, *Remote*. "
            "Leave empty to see everything."
        )

    # Apply the location filter to every job (and regroup afterwards).
    loc_lower = (location_query or "").strip().lower()
    if loc_lower:
        filtered: list = []
        for job in jobs:
            job_loc = (job.get("location") or "").lower()
            if loc_lower in job_loc:
                filtered.append(job)
                continue
            # Fuzzy city synonyms: Bangalore <-> Bengaluru, Mumbai <-> Bombay.
            synonyms = {
                "bangalore": ["bengaluru"],
                "bengaluru": ["bangalore"],
                "mumbai": ["bombay"],
                "bombay": ["mumbai"],
                "delhi": ["new delhi", "ncr"],
                "hyderabad": ["secunderabad"],
            }
            for canonical, alts in synonyms.items():
                if loc_lower == canonical and any(a in job_loc for a in alts):
                    filtered.append(job)
                    break
                if loc_lower in alts and canonical in job_loc:
                    filtered.append(job)
                    break
        jobs = filtered
        # Regroup after filtering.
        grouped = {}
        for job in jobs:
            domain = classify_domain(job.get("title", ""))
            grouped.setdefault(domain, []).append(job)
        domains_present = [d for d in _DOMAIN_ORDER if d in grouped]
        fresh_count = sum(1 for j in jobs if _is_fresh_24h(j.get("posted_at")))

    if not jobs:
        st.info("No jobs match the current location filter.")
        return

    # Category filter (pills).
    options = ["All"] + domains_present
    labels = {"All": "All categories"}
    for d in domains_present:
        labels[d] = f"{_DOMAIN_LABELS.get(d, d)} ({len(grouped[d])})"
    selected = _category_picker(options, labels)

    # Resume match % on every card — one click, cached in the session.
    match_scores: dict = st.session_state.get("saved_job_match_scores") or {}
    if st.button("🎯 Match these jobs to my resume", use_container_width=True):
        with st.spinner("Matching against your resume..."):
            job_ids = [j["id"] for j in jobs if j.get("id")][:50]
            if job_ids:
                result = _api(
                    f"/resumes/match-batch?user_id={_current_user_id()}&job_ids="
                    + "&job_ids=".join(job_ids),
                    method="POST",
                    timeout=45,
                )
                if result and result.get("matches"):
                    match_scores = {
                        m.get("job_id"): m.get("match_score") for m in result["matches"]
                    }
                    st.session_state["saved_job_match_scores"] = match_scores
                    st.success(
                        f"✅ Matched {len(match_scores)} jobs — average "
                        f"{result.get('average_score')}%"
                    )
                else:
                    st.info(
                        "No match scores — upload your resume on the Resume "
                        "Match page first."
                    )
    elif not match_scores:
        st.caption(
            "💡 Click **Match these jobs to my resume** to see your match % on "
            "every card."
        )

    # Render sections.
    domains = domains_present if selected == "All" else [selected]
    for domain in domains:
        items = grouped.get(domain)
        if not items:
            continue
        _category_header(domain, len(items), len(jobs))
        for job in items:
            _render_job(job, match_scores.get(job.get("id")))


def _share_job_form() -> None:
    """Share-a-job form: paste any job link to save it and include in alerts."""
    st.markdown(
        '<div class="section-title">Share a Job You Found</div>'
        '<div class="section-sub">Found a role on LinkedIn, a company site, or '
        "anywhere else? Paste the link — the app saves it and it appears in "
        "your Saved Jobs and daily alerts.</div>",
        unsafe_allow_html=True,
    )

    with st.form("share_job_form", clear_on_submit=True):
        url = st.text_input(
            "Job link *",
            placeholder="https://www.linkedin.com/jobs/view/... or any careers page",
        )
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Job title (optional)", placeholder="SOC Analyst")
        with col2:
            company = st.text_input("Company (optional)", placeholder="Acme Corp")
        location = st.text_input(
            "Location (optional)", placeholder="Remote / Bengaluru"
        )
        submitted = st.form_submit_button("💾 Save Job", use_container_width=True)

    if submitted:
        if not url or not url.strip().startswith(("http://", "https://")):
            st.error("Please paste a valid job link (https://...).")
            return
        payload = {"url": url.strip()}
        if title:
            payload["title"] = title.strip()
        if company:
            payload["company"] = company.strip()
        if location:
            payload["location"] = location.strip()
        with st.spinner("Saving job..."):
            resp = _api_raw("/jobs/share", method="POST", json_data=payload, timeout=45)
        if resp is None:
            st.error("Share API unreachable. Is the API server running?")
        elif resp.status_code == 200:
            data = resp.json()
            if data.get("duplicate"):
                st.info("ℹ️ This job was already saved — no duplicate created.")
            else:
                job = data.get("job", {})
                st.success(
                    f"✅ Saved **{job.get('title')}** at **{job.get('company')}**!"
                )
                st.caption("It's now in Saved Jobs and included in your daily alerts.")
        else:
            detail = ""
            with suppress(Exception):
                detail = resp.json().get("detail", "")
            st.error(
                f"Couldn't save the job. "
                f"{detail or 'Please fill in the title and company manually.'}"
            )
        st.caption(
            "💡 Tip: if auto-detection can't read a link, just paste the title "
            "and company too — that always works."
        )


# ---------------------------------------------------------------------------
# Page: Applications
# ---------------------------------------------------------------------------


def show_applications() -> None:
    """Show and manage applications."""
    st.header("📋 Applications")

    status_filter = st.selectbox(
        "Filter by status",
        [
            "All",
            "saved",
            "applied",
            "interview",
            "assessment",
            "rejected",
            "offer",
            "joined",
        ],
    )

    endpoint = (
        "/applications/"
        if status_filter == "All"
        else f"/applications/?status={status_filter}"
    )
    apps_data = fetch_data(endpoint)

    if apps_data and apps_data.get("applications"):
        for app in apps_data["applications"]:
            with st.expander(
                f"Application {app.get('id', '?')[:8]}... — {app.get('status', 'saved')}"
            ):
                st.write(f"Job ID: {app.get('job_id', 'N/A')}")
                st.write(f"Created: {app.get('created_at', 'N/A')}")

                new_status = st.selectbox(
                    "Update status",
                    [
                        "saved",
                        "applied",
                        "interview",
                        "assessment",
                        "rejected",
                        "offer",
                        "joined",
                    ],
                    key=f"status_{app['id']}",
                )
                if st.button(
                    "Update", key=f"update_{app['id']}", use_container_width=True
                ):
                    _update_application_status(app["id"], new_status)
    else:
        st.info("No applications found. Apply to jobs from the Jobs page!")


# ---------------------------------------------------------------------------
# Page: Watchlist
# ---------------------------------------------------------------------------


def show_watchlist() -> None:
    """Track companies and surface their active job openings.

    Watched companies get a dedicated "🏢 Watched companies" section in
    the daily email/Telegram digest, so this page is the management UI for
    that alert feature (the API and digest integration already exist).
    """
    st.header("🏢 Company Watchlist")
    st.markdown(
        "Watch companies you're targeting — their jobs get a dedicated section "
        "in your daily digest, and you can see every open role below."
    )
    user_id = _current_user_id()

    # ── Add a company ──────────────────────────────────────────────────
    with st.form("watchlist_add_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            company = st.text_input(
                "Company name", placeholder="e.g. Zscaler, CrowdStrike, Google"
            )
        with col2:
            notes = st.text_input(
                "Notes (optional)", placeholder="targeting SOC roles here"
            )
        with col3:
            st.write("")
            added = st.form_submit_button("➕ Watch", use_container_width=True)

    if added:
        if not company.strip():
            st.error("Please enter a company name.")
        else:
            resp = _api_raw(
                "/watchlists",
                method="POST",
                json_data={
                    "user_id": user_id,
                    "company": company.strip(),
                    "notes": notes.strip() or None,
                },
                timeout=20,
            )
            if resp is not None and resp.status_code == 201:
                st.success(
                    f"✅ Now watching **{company.strip()}** — its jobs appear in your daily digest."
                )
                st.rerun()
            elif resp is not None and resp.status_code == 409:
                st.info(f"ℹ️ **{company.strip()}** is already on your watchlist.")
            else:
                st.error("Could not add the company — is the API server running?")

    st.divider()

    # ── Current watchlist ──────────────────────────────────────────────
    data = fetch_data(f"/watchlists?user_id={user_id}")
    if not data or not data.get("watchlist"):
        st.info(
            "No companies watched yet. Add one above (e.g. **Zscaler**, **Okta**, "
            "**Cloudflare**) — their new jobs are highlighted in your daily "
            "email and Telegram alerts."
        )
        return

    watchlist = data["watchlist"]
    st.subheader(f"Your companies ({data.get('total', len(watchlist))})")

    for item in watchlist:
        company_name = escape(str(item.get("company", "Unknown")))
        active = int(item.get("active_jobs", 0) or 0)
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(
                    f'<div class="job-title">{company_name}</div>',
                    unsafe_allow_html=True,
                )
                if item.get("notes"):
                    st.caption(f"📝 {escape(str(item['notes']))}")
            with col2:
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<div style="font-size:1.6em;font-weight:800;color:#3b82f6;">{active}</div>'
                    f'<div style="color:#94a3b8;font-size:0.75em;">active jobs</div></div>',
                    unsafe_allow_html=True,
                )
            with col3:
                if st.button(
                    "🗑 Remove",
                    key=f"unwatch_{item.get('id')}",
                    use_container_width=True,
                ):
                    resp = _api_raw(
                        f"/watchlists/{item.get('id')}", method="DELETE", timeout=20
                    )
                    if resp is not None and resp.status_code in (200, 204):
                        st.success(f"Removed **{company_name}** from your watchlist.")
                        st.rerun()
                    else:
                        st.error("Could not remove the company.")

    st.divider()
    st.caption(
        "💡 Watched-company jobs lead a dedicated section in your daily digest, "
        "so you never miss a posting from your target employers."
    )


# ---------------------------------------------------------------------------
# Page: Analytics
# ---------------------------------------------------------------------------


def show_analytics() -> None:
    """Show analytics page."""
    st.header("📈 Analytics")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Application Timeline")
        timeline = fetch_data("/dashboard/charts/application-timeline")
        if timeline and timeline.get("data"):
            import pandas as pd

            df = pd.DataFrame(timeline["data"])
            if not df.empty:
                st.plotly_chart(
                    px.line(df, x="date", y="count", color="status"),
                    use_container_width=True,
                )

    with col2:
        st.subheader("Top Companies")
        companies = fetch_data("/dashboard/charts/top-companies")
        if companies and companies.get("data"):
            import pandas as pd

            df = pd.DataFrame(companies["data"])
            if not df.empty:
                st.plotly_chart(
                    px.bar(df, x="company", y="count"),
                    use_container_width=True,
                )

    st.subheader("💰 Salary Statistics")
    salary = fetch_data("/dashboard/charts/salary")
    if salary and salary.get("data"):
        data = salary["data"]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            val = data.get("min_salary")
            st.metric("Min Salary", f"${val:,.0f}" if val else "N/A")
        with col2:
            val = data.get("max_salary")
            st.metric("Max Salary", f"${val:,.0f}" if val else "N/A")
        with col3:
            val = data.get("avg_min")
            st.metric("Avg Min", f"${val:,.0f}" if val else "N/A")
        with col4:
            val = data.get("avg_max")
            st.metric("Avg Max", f"${val:,.0f}" if val else "N/A")


# ---------------------------------------------------------------------------
# Page: Resume Match
# ---------------------------------------------------------------------------


def show_resume_match() -> None:
    """Upload a resume and match against saved jobs."""
    st.header("🎯 Resume Match")
    st.markdown(
        "Upload your resume (PDF) and we'll match your skills against all saved jobs."
    )

    # User ID — the logged-in account (or the legacy user1 default).
    user_id = _current_user_id()
    if _current_user():
        st.caption(
            f"👤 Matching as **{_current_user().get('name', '')}** — your resume "
            "is stored separately from other users'."
        )
    else:
        st.caption(
            "👤 Not signed in — using **user1**. Create an account on the "
            "*My Account* page to get your own personalized matching."
        )

    # Upload
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

    if uploaded_file and st.button(
        "📤 Upload & Parse Resume", use_container_width=True
    ):
        with st.spinner("Parsing your resume..."):
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    "application/pdf",
                )
            }
            result = _api(
                f"/resumes/upload?user_id={user_id}",
                method="POST",
                files=files,
                timeout=30,
            )
            if result:
                st.success("✅ Resume parsed successfully!")
                skills = result.get("skills", [])
                education = result.get("education", [])
                experience = result.get("experience", [])
                certs = result.get("certifications", [])

                if skills:
                    st.subheader("🧠 Skills Detected")
                    skill_names = [
                        s.get("name", str(s)) if isinstance(s, dict) else str(s)
                        for s in skills
                    ]
                    st.write(", ".join(skill_names[:20]))
                    if len(skill_names) > 20:
                        st.caption(f"...and {len(skill_names) - 20} more")

                if education:
                    st.subheader("🎓 Education")
                    for edu in education:
                        st.write(
                            f"- {edu.get('degree', 'N/A')} at {edu.get('institution', 'N/A')}"
                        )

                if experience:
                    st.subheader("💼 Experience")
                    for exp in experience[:5]:
                        st.write(f"- {exp.get('role', 'N/A')}")

                if certs:
                    st.subheader("📜 Certifications")
                    for c in certs:
                        st.write(
                            f"- {c.get('name', 'N/A')} ({c.get('status', 'completed')})"
                        )
            else:
                st.error("Failed to parse resume. Make sure it's a valid PDF.")

    st.divider()

    # Match against jobs
    st.subheader("📊 Match Against Jobs")
    if st.button("🔍 Find Best Matching Jobs", use_container_width=True):
        with st.spinner("Matching your skills against all jobs..."):
            # Get all jobs
            jobs_data = fetch_data("/jobs/?limit=50")
            if not jobs_data or not jobs_data.get("jobs"):
                st.info("No jobs to match against. Run discovery first!")
                return

            job_ids = [j["id"] for j in jobs_data["jobs"] if j.get("id")]
            if not job_ids:
                st.info("No valid job IDs found.")
                return

            # Batch match
            result = _api(
                f"/resumes/match-batch?user_id={user_id}&job_ids={'&job_ids='.join(job_ids)}",
                method="POST",
                timeout=30,
            )
            if result:
                matches = result.get("matches", [])
                if matches:
                    st.success(f"✅ Matched against **{len(matches)}** jobs!")
                    avg = result.get("average_score")
                    if avg is not None:
                        st.metric("Average Match Score", f"{avg}%")

                    for m in matches[:10]:
                        score = m.get("match_score", 0)
                        color = (
                            "🟢"
                            if (score or 0) >= 70
                            else "🟡"
                            if (score or 0) >= 40
                            else "🔴"
                        )
                        ats = m.get("ats_score")
                        ats_tag = ""
                        if ats is not None:
                            ats_tag = f" · ATS: {ats:.0f}%"
                        with st.expander(
                            f"{color} **{m.get('job_title', 'N/A')}** at {m.get('company', 'N/A')} — Match: {score or 0}%{ats_tag}"
                        ):
                            matched = m.get("matched_skills", [])
                            related = m.get("related_skills", [])
                            missing = m.get("missing_skills", [])
                            if matched:
                                st.write(
                                    "✅ **Your matched skills:**",
                                    ", ".join(matched[:10]),
                                )
                            if related:
                                st.write(
                                    "🔗 **Transferable skills (same domain):**",
                                    ", ".join(related[:10]),
                                )
                            if missing:
                                st.write(
                                    "📚 **Skills to learn:**", ", ".join(missing[:10])
                                )
                            suggestions = m.get("suggestions", [])
                            if suggestions:
                                st.write("💡 **Suggestions:**")
                                for s in suggestions:
                                    st.write(f"- {s}")
                            ats_feedback = m.get("ats_feedback", [])
                            if ats_feedback:
                                st.write("📄 **ATS improvements:**")
                                for s in ats_feedback:
                                    st.write(f"- {s}")
                else:
                    st.info("No matches found. Upload your resume first!")
            else:
                st.error("Match API unavailable. Upload your resume first!")

    st.divider()
    st.caption(
        "💡 Upload your resume once — it's saved in the database. You can re-match anytime as new jobs are discovered."
    )


# ---------------------------------------------------------------------------
# Page: Learning
# ---------------------------------------------------------------------------


def show_salary_insights() -> None:
    """Show salary insights dashboard."""
    st.header("Salary Insights")
    st.markdown("Salary statistics by domain, location, and company")

    col1, col2 = st.columns(2)
    with col1:
        domain = st.selectbox(
            "Domain",
            ["All", "security", "development", "data", "devops", "design"],
        )
    with col2:
        location = st.text_input("Location filter", placeholder="e.g. Bangalore")

    params = {}
    if domain != "All":
        params["domain"] = domain
    if location:
        params["location"] = location

    data = _api("/salary/overview", params=params)
    if data and data.get("overall"):
        overall = data["overall"]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Salary", f"${overall['avg']:,}")
        with col2:
            st.metric("Min Salary", f"${overall['min']:,}")
        with col3:
            st.metric("Max Salary", f"${overall['max']:,}")
        with col4:
            st.metric("Jobs with Salary", data.get("jobs_with_salary", 0))

        if data.get("by_domain"):
            st.subheader("By Domain")
            for d, stats in data["by_domain"].items():
                if stats:
                    st.write(
                        f"**{d.title()}**: ${stats['min']:,} - ${stats['max']:,} (avg: ${stats['avg']:,}, {stats['count']} jobs)"
                    )

        if data.get("by_location"):
            st.subheader("Top Locations")
            for loc, stats in list(data["by_location"].items())[:5]:
                if stats:
                    st.write(
                        f"**{loc}**: ${stats['min']:,} - ${stats['max']:,} (avg: ${stats['avg']:,})"
                    )
    else:
        st.info(
            "No salary data available yet. Run discovery to find jobs with salary info."
        )


def show_weekly_digest() -> None:
    """Show weekly digest summary."""
    st.header("Weekly Digest")
    st.markdown("Your weekly job market summary")

    data = _api("/digest/summary")
    if data:
        jobs = data.get("jobs", {})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Jobs This Week", jobs.get("this_week", 0), jobs.get("trend_pct", 0)
            )
        with col2:
            st.metric("Applications", data.get("applications", {}).get("this_week", 0))
        with col3:
            trend = jobs.get("trend", "new")
            st.metric("Market Trend", trend.upper())

        highlights = data.get("highlights", [])
        if highlights:
            st.subheader("Highlights")
            for h in highlights:
                if h:
                    st.write(h)

        companies = data.get("new_companies", [])
        if companies:
            st.subheader("New Companies This Week")
            st.write(", ".join(companies[:10]))

        skills = data.get("top_skills", [])
        if skills:
            st.subheader("Top Skills in Demand")
            for s in skills[:5]:
                st.write(f"- {s['skill']} ({s['count']} jobs)")
    else:
        st.info("No weekly data available yet.")


def show_bookmarks() -> None:
    """Show saved job bookmarks."""
    st.header("Bookmarks")
    st.markdown("Your saved jobs for later")

    col1, col2 = st.columns(2)
    with col1:
        tag_filter = st.text_input("Filter by tag")
    with col2:
        st.write("")

    params = {}
    if tag_filter:
        params["tag"] = tag_filter

    data = _api("/bookmarks", params=params)
    if data and data.get("bookmarks"):
        for bm in data["bookmarks"]:
            job = bm.get("job", {})
            if job:
                with st.container():
                    col1, col2, col3 = st.columns([4, 2, 1])
                    with col1:
                        st.markdown(f"**{job.get('title', 'Unknown')}**")
                        st.caption(
                            f"{job.get('company', 'Unknown')} | {job.get('location', 'Remote')}"
                        )
                    with col2:
                        if bm.get("tags"):
                            st.caption(f"Tags: {', '.join(bm['tags'])}")
                        if bm.get("notes"):
                            st.caption(f"Note: {bm['notes'][:50]}")
                    with col3:
                        if job.get("url"):
                            st.link_button("View", job["url"], use_container_width=True)
                    st.divider()
    else:
        st.info("No bookmarks yet. Save jobs from the Jobs page!")
        st.subheader("How to Bookmark")
        st.write("1. Go to Jobs page")
        st.write("2. Run discovery to find jobs")
        st.write("3. Click Save on any job you like")
        st.write("4. Come back here to see your saved jobs")


def show_expired() -> None:
    """Show expired/archived jobs."""
    st.header("Expired Jobs")
    st.markdown("Jobs older than 30 days are automatically archived here")

    # Archive button
    if st.button("Archive Old Jobs Now", type="secondary"):
        with st.spinner("Archiving old jobs..."):
            result = _api("/jobs/archive-expired", method="POST", params={"days": 30})
            if result:
                st.success(f"Archived {result.get('archived', 0)} jobs")
            else:
                st.error("Archive failed")

    # List expired jobs
    data = _api("/jobs/expired", params={"limit": 100})
    if data and data.get("expired_jobs"):
        st.subheader(f"Archived Jobs ({data.get('total', 0)})")
        for job in data["expired_jobs"]:
            with st.container():
                col1, col2, col3 = st.columns([4, 2, 1])
                with col1:
                    st.markdown(f"**{job.get('title', 'Unknown')}**")
                    st.caption(
                        f"{job.get('company', 'Unknown')} | {job.get('location', 'Remote')}"
                    )
                with col2:
                    st.caption(f"Source: {job.get('source', 'unknown')}")
                    st.caption(f"Expired: {job.get('expired_at', 'N/A')}")
                with col3:
                    if job.get("reason"):
                        st.caption(f"Reason: {job['reason']}")
                st.divider()
    else:
        st.info(
            "No expired jobs yet. Jobs older than 30 days will be archived automatically."
        )


def show_learning() -> None:
    """Show learning resources."""
    st.header("📚 Learning Resources")

    platforms = [
        {
            "name": "Google Cloud Skills Boost",
            "icon": "☁️",
            "url": "https://cloudskillsboost.google",
        },
        {"name": "OWASP", "icon": "🔒", "url": "https://owasp.org"},
        {
            "name": "PortSwigger",
            "icon": "🎯",
            "url": "https://portswigger.net/web-security",
        },
        {"name": "TryHackMe", "icon": "🏴‍☠️", "url": "https://tryhackme.com"},
        {"name": "Hack The Box", "icon": "📦", "url": "https://hackthebox.com"},
        {"name": "OverTheWire", "icon": "🎯", "url": "https://overthewire.org"},
        {"name": "PicoCTF", "icon": "🏆", "url": "https://picoctf.org"},
    ]

    cols = st.columns(3)
    for i, platform in enumerate(platforms):
        with cols[i % 3], st.container(border=True):
            st.markdown(f"### {platform['icon']} {platform['name']}")
            st.link_button("Visit", platform["url"], use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Settings
# ---------------------------------------------------------------------------


_NOTIF_CHANNEL_LABELS = {
    "email": "📧 Email",
    "telegram": "✈️ Telegram",
    "discord": "🎮 Discord",
    "slack": "💬 Slack",
}


def show_settings() -> None:
    """Show settings page."""
    st.header("⚙️ Settings")

    # ------------------------------------------------------------------
    # 🔔 Notifications — daily job alert preferences
    # ------------------------------------------------------------------
    st.subheader("🔔 Notifications")

    # Visual flow explaining how notifications work
    st.markdown(
        "<div style='background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);"
        "border-radius:16px;padding:24px 28px;color:white;margin-bottom:20px;'>"
        "<div style='font-size:18px;font-weight:800;margin-bottom:12px;'>"
        "How your daily job alerts work</div>"
        "<div style='display:flex;gap:16px;flex-wrap:wrap;'>"
        "<div style='flex:1;min-width:140px;background:rgba(255,255,255,0.15);"
        "border-radius:12px;padding:14px;text-align:center;'>"
        "<div style='font-size:28px;'>🔍</div>"
        "<div style='font-weight:700;font-size:13px;margin:4px 0;'>1. Discover</div>"
        "<div style='font-size:11px;opacity:0.85;'>Scrapers find new jobs from "
        "LinkedIn, RemoteOK, HackerNews and more, 3x daily</div></div>"
        "<div style='flex:1;min-width:140px;background:rgba(255,255,255,0.15);"
        "border-radius:12px;padding:14px;text-align:center;'>"
        "<div style='font-size:28px;'>🎯</div>"
        "<div style='font-weight:700;font-size:13px;margin:4px 0;'>2. Match</div>"
        "<div style='font-size:11px;opacity:0.85;'>Filtered by your categories, "
        "location, and resume match % - only relevant jobs kept</div></div>"
        "<div style='flex:1;min-width:140px;background:rgba(255,255,255,0.15);"
        "border-radius:12px;padding:14px;text-align:center;'>"
        "<div style='font-size:28px;'>📬</div>"
        "<div style='font-weight:700;font-size:13px;margin:4px 0;'>3. Deliver</div>"
        "<div style='font-size:11px;opacity:0.85;'>Styled HTML email and Telegram "
        "sent at 08:00, 13:00, 19:00 IST with Apply buttons</div></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    # Which channels are actually configured on the API?
    channels_data = fetch_data("/notifications/channels") or {}
    configured = channels_data.get("channels") or []
    if not configured:
        st.warning(
            "⚠️ No notification channels are configured on the API yet. "
            "Add `SMTP_USER` / `SMTP_PASSWORD` (email) and `TELEGRAM_BOT_TOKEN` / "
            "`TELEGRAM_CHAT_ID` in the Vercel project env vars."
        )
    else:
        st.caption(
            "Configured channels: "
            + " · ".join(
                f"✅ **{_NOTIF_CHANNEL_LABELS.get(c, c)}**" for c in configured
            )
        )

    user_id = _current_user_id()
    if _current_user():
        st.caption(f"👤 Alert preferences for **{_current_user().get('name', '')}**.")
    else:
        st.caption("👤 Not signed in — editing **user1** preferences.")
    prefs = fetch_data(f"/notifications/preferences/{user_id}") or {}
    saved_chans = prefs.get("channels") or []
    saved_domains = prefs.get("domains") or []
    saved_min = prefs.get("min_match_score") or 0
    saved_location = prefs.get("location") or ""

    # Channel status indicators
    if configured:
        st.markdown("**📤 Delivery channels**")
        chan_cols = st.columns(len(configured) if len(configured) <= 3 else 3)
        for i, ch in enumerate(configured):
            label = _NOTIF_CHANNEL_LABELS.get(ch, ch)
            is_active = ch in saved_chans or not saved_chans
            icon = "✅" if is_active else "⬜"
            with chan_cols[i % len(chan_cols)]:
                st.markdown(
                    f"<div style='padding:8px 14px;border-radius:8px;"
                    f"background:{'#dcfce7' if is_active else '#f1f5f9'};"
                    f"border:1px solid {'#86efac' if is_active else '#e2e8f0'};'>"
                    f"<b>{icon} {label}</b></div>",
                    unsafe_allow_html=True,
                )

    # Location
    st.markdown("---")
    st.markdown(
        "**📍 Preferred location** - Jobs in your area appear first in the "
        "daily email. Works with fuzzy matching (e.g. Bangalore also "
        "matches Bengaluru)."
    )
    location = st.text_input(
        "Your city",
        value=saved_location,
        placeholder="e.g. Bangalore, Mumbai, Delhi",
        help="Leave empty to see jobs from all locations.",
    )

    # Channels to deliver alerts through.
    chan_options = [c for c in ("email", "telegram") if c in configured]
    default_chans = [c for c in chan_options if c in saved_chans] or chan_options
    selected_chans = st.multiselect(
        "📤 Send alerts via",
        chan_options or ["email", "telegram"],
        default=default_chans,
        format_func=lambda c: _NOTIF_CHANNEL_LABELS.get(c, c),
    )

    # Categories to receive (multi-pills, "All categories" = everything).
    default_domains = saved_domains or ["all"]
    selected_domains = _category_picker_multi(
        "🏷 Categories to receive", default_domains
    )
    # Empty domains = every category.
    domains = [] if "all" in selected_domains else selected_domains

    # Per-time-slot categories: each of the 3 daily sends can carry its own.
    st.markdown(
        "**🕐 Per-slot categories (optional)** — your 3 daily sends can each "
        "focus on a different category. Leave a slot on *All* to use the "
        "general selection above."
    )
    slot_domains = prefs.get("slot_domains") or {}
    slot_picks = {}
    for slot_key, slot_label in (
        ("morning", "🌅 Morning (08:00 IST)"),
        ("afternoon", "☀️ Afternoon (13:00 IST)"),
        ("evening", "🌙 Evening (19:00 IST)"),
    ):
        saved_slot = slot_domains.get(slot_key) or []
        default_slot = saved_slot or ["all"]
        picked = _category_picker_multi(f"{slot_label} — categories", default_slot)
        slot_picks[slot_key] = [] if "all" in picked else picked

    weekly_enabled = st.checkbox(
        "📅 Send a Sunday weekly digest (recap of the week's jobs)",
        value=bool(prefs.get("weekly_enabled", True)),
    )

    # Optional minimum resume-match threshold.
    min_score = st.slider(
        "🎯 Only show jobs matching at least",
        0,
        100,
        int(saved_min or 0),
        help="0 = no filter. Uses your uploaded resume's match % per job.",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Alert Preferences", use_container_width=True):
            payload = {
                "domains": domains,
                "channels": selected_chans or chan_options or ["email", "telegram"],
                "min_match_score": min_score or None,
                "is_enabled": True,
                "slot_domains": slot_picks,
                "weekly_enabled": weekly_enabled,
                "location": location.strip() or None,
            }
            result = _api(
                f"/notifications/preferences/{user_id}",
                method="PUT",
                json_data=payload,
                timeout=30,
            )
            if result:
                cats = (
                    _DOMAIN_LABELS.get(domains[0], domains[0])
                    if len(domains) == 1
                    else (f"{len(domains)} categories" if domains else "all categories")
                )
                extra = ""
                if any(slot_picks.values()):
                    extra = " + per-slot categories"
                st.success(
                    f"✅ Preferences saved! Your daily alert now sends **{cats}** "
                    f"via {', '.join(result.get('channels') or payload['channels'])}"
                    f"{extra}. Weekly digest: {'on' if weekly_enabled else 'off'}."
                )
                # Also save location to user profile
                if location.strip():
                    _api(
                        f"/users/{user_id}",
                        method="PUT",
                        json_data={"location": location.strip()},
                        timeout=15,
                    )
            else:
                st.error("Failed to save preferences — is the API reachable?")

    with col2:
        if st.button("🚀 Send Test Alert Now", use_container_width=True):
            with st.spinner("Building your filtered alert and sending..."):
                result = _api(
                    f"/notifications/preferences/{user_id}/send-alert",
                    method="POST",
                    timeout=120,
                )
                if result:
                    results = result.get("results") or {}
                    delivered = [
                        _NOTIF_CHANNEL_LABELS.get(c, c)
                        for c, ok in results.items()
                        if ok
                    ]
                    if delivered:
                        st.success(
                            f"✅ Sent **{result.get('job_count', 0)} matching jobs** "
                            f"via {', '.join(delivered)}!"
                        )
                    else:
                        st.error(
                            f"Alert had {result.get('job_count', 0)} jobs but delivery "
                            f"failed: {results}"
                        )
                else:
                    st.error("Send failed — is the API reachable and configured?")

    if domains:
        st.caption(
            "🔔 Your daily alert is filtered to: "
            + ", ".join(_DOMAIN_LABELS.get(d, d) for d in domains)
        )

    if any(slot_picks.values()):
        st.caption(
            "🕐 Per-slot: "
            + " · ".join(
                f"{label.split(' (')[0]}: "
                + (
                    ", ".join(_DOMAIN_LABELS.get(d, d) for d in slot_picks[k])
                    if slot_picks[k]
                    else "general selection"
                )
                for k, label in (
                    ("morning", "🌅 Morning (08:00 IST)"),
                    ("afternoon", "☀️ Afternoon (13:00 IST)"),
                    ("evening", "🌙 Evening (19:00 IST)"),
                )
            )
        )

    # --------------------------------------------------------------
    # 🧪 One-off alert — test any categories without saving
    # --------------------------------------------------------------
    with st.expander("🧪 One-off alert — test any categories right now"):
        st.markdown(
            "Send a **single alert** with any categories you like. This does "
            "**not** change your saved preferences above."
        )

        oneoff_selected = _category_picker_multi(
            "Categories for this one-off alert", default_domains
        )
        oneoff_domains = [] if "all" in oneoff_selected else oneoff_selected
        oneoff_chans = st.multiselect(
            "Deliver this one-off alert via",
            chan_options or ["email", "telegram"],
            default=default_chans,
            format_func=lambda c: _NOTIF_CHANNEL_LABELS.get(c, c),
        )

        if st.button("🚀 Send This One-Off Alert", use_container_width=True):
            with st.spinner("Building and sending your one-off alert..."):
                payload = {"domains": oneoff_domains, "channels": oneoff_chans}
                result = _api(
                    f"/notifications/preferences/{user_id}/send-alert",
                    method="POST",
                    json_data=payload,
                    timeout=120,
                )
                if result:
                    results = result.get("results") or {}
                    delivered = [
                        _NOTIF_CHANNEL_LABELS.get(c, c)
                        for c, ok in results.items()
                        if ok
                    ]
                    if delivered:
                        cats = (
                            "all categories"
                            if not oneoff_domains
                            else ", ".join(
                                _DOMAIN_LABELS.get(d, d) for d in oneoff_domains
                            )
                        )
                        st.success(
                            f"✅ One-off alert sent — **{result.get('job_count', 0)} "
                            f"jobs** ({cats}) via {', '.join(delivered)}. "
                            "Saved preferences were not changed."
                        )
                    else:
                        st.error(
                            f"One-off alert had {result.get('job_count', 0)} jobs "
                            f"but delivery failed: {results}"
                        )
                else:
                    st.error("One-off alert failed — is the API reachable?")

    st.markdown("")

    # --------------------------------------------------------------
    # 🕘 Recent Alerts — send history
    # --------------------------------------------------------------
    st.subheader("🕘 Recent Alerts")
    history_data = (
        fetch_data(f"/notifications/preferences/{user_id}/history?limit=15") or {}
    )
    history = history_data.get("history") or []
    if not history:
        st.caption(
            "No alerts sent yet — use **Send Test Alert Now** above or wait "
            "for the daily digest (08:00 / 13:00 / 19:00 IST, Kolkata)."
        )
    else:
        import pandas as pd

        rows = []
        for h in history:
            delivered = [
                _NOTIF_CHANNEL_LABELS.get(c, c)
                for c, ok in (h.get("results") or {}).items()
                if ok
            ]
            rows.append(
                {
                    "Sent (IST)": _ist_time(h.get("sent_at")),
                    "Subject": h.get("subject") or "",
                    "Channels": ", ".join(h.get("channels") or []) or "—",
                    "Categories": ", ".join(h.get("domains") or []) or "all",
                    "Jobs": h.get("job_count") or 0,
                    "Delivered": ", ".join(delivered) or "❌ none",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Every manual test, one-off alert and scheduled digest is recorded here. "
            "Alerts only include **new jobs** since the previous send (no repeats). "
            "Sends run at 08:00 / 13:00 / 19:00 IST (+ a Sunday weekly recap), and "
            "Telegram alerts now carry tap-to-apply buttons."
        )

    # Preview section
    st.markdown("---")
    with st.expander("Preview: What your daily email looks like", expanded=False):
        st.markdown(
            "<div style='font-family:Inter,sans-serif;max-width:100%;"
            "background:white;border-radius:14px;overflow:hidden;"
            "border:1px solid #e2e8f0;margin-top:8px;'>"
            "<div style='background:linear-gradient(135deg,#667eea,#764ba2);"
            "color:white;padding:18px 22px;'>"
            "<div style='font-size:16px;font-weight:800;'>Daily Report</div>"
            "<div style='opacity:0.85;font-size:11px;'>Today - 3x per day</div>"
            "<div style='margin-top:8px;font-size:13px;'>"
            "New jobs: <b>8</b> | Applied: <b>2</b></div></div>"
            "<div style='padding:16px;'>"
            "<div style='color:#64748b;font-size:12px;font-weight:600;"
            "margin-bottom:8px;'>Security</div>"
            "<div style='border:1px solid #e2e8f0;border-radius:10px;"
            "padding:12px 14px;margin-bottom:8px;'>"
            "<div style='display:flex;justify-content:space-between;'>"
            "<div><b>SOC Analyst</b></div>"
            "<div style='font-size:18px;font-weight:800;color:#e5484d;'>85%</div></div>"
            "<div style='color:#64748b;font-size:12px;'>"
            "Acme Security - Bangalore - Posted 2d ago</div>"
            "<div style='margin-top:8px;'>"
            "<span style='background:#e5484d;color:white;border-radius:6px;"
            "padding:4px 12px;font-size:11px;font-weight:600;'>Apply now</span>"
            "</div></div>"
            "<div style='color:#94a3b8;font-size:10px;padding:0 16px 14px;'>"
            "Match % = resume fit | Applied/Not applied</div>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "This is a sample - your actual email will show your matched jobs "
            "with real apply links, match scores, and expiry badges."
        )

    st.divider()

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------
    st.subheader("About")
    st.write(f"**InternTrack** v{fetch_version()}")
    st.write("AI-powered internship and job tracking platform")
    st.write(f"API: `{API_URL}`")

    if st.button("🔄 Clear Cache & Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
