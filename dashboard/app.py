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

# Accent styles per category (color = badge/bar accent, grad = icon tile).
_CATEGORY_STYLE = {
    "security": {"color": "#e5484d", "grad": "linear-gradient(135deg,#ff6b6b,#c0392b)"},
    "coding": {"color": "#3b82f6", "grad": "linear-gradient(135deg,#60a5fa,#1d4ed8)"},
    "data": {"color": "#8b5cf6", "grad": "linear-gradient(135deg,#a78bfa,#6d28d9)"},
    "design": {"color": "#ec4899", "grad": "linear-gradient(135deg,#f472b6,#be185d)"},
    "finance": {"color": "#10b981", "grad": "linear-gradient(135deg,#34d399,#047857)"},
    "marketing": {
        "color": "#f59e0b",
        "grad": "linear-gradient(135deg,#fbbf24,#b45309)",
    },
    "other": {"color": "#64748b", "grad": "linear-gradient(135deg,#94a3b8,#475569)"},
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
        f"{style['icon']}</span>"
        f'<span class="cat-name">{_DOMAIN_LABELS.get(domain, domain)}</span>'
        f'<span class="cat-badge" style="background:{style["color"]}">{count}</span>'
        f'<span class="cat-pct">{pct:.0f}% of jobs</span></div>'
        f'<div class="cat-bar"><div class="cat-bar-fill" '
        f'style="width:{pct:.1f}%;background:{style["color"]}"></div></div>',
        unsafe_allow_html=True,
    )


def _render_job(job: dict) -> None:
    """One job as a clean, hoverable card with real widgets.

    All scraped fields (title, company, location, description, ...) are
    untrusted external content, so every value interpolated into HTML is
    escaped before rendering with ``unsafe_allow_html``.
    """
    title = escape(str(job.get("title", "Untitled")))
    company = escape(str(job.get("company", "Unknown")))
    posted = job.get("posted_at")

    with st.container(border=True):
        col_l, col_r = st.columns([4, 1])

        with col_l:
            st.markdown(f'<div class="job-title">{title}</div>', unsafe_allow_html=True)

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
                st.toast("Application tracked! Visit Applications to update status.")


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

    tab1, tab2 = st.tabs(["🔍 Discovery", "📋 Saved Jobs"])

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
            return

        jobs = jobs_data["jobs"]

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

        # Category filter (pills).
        options = ["All"] + domains_present
        labels = {"All": "All categories"}
        for d in domains_present:
            labels[d] = f"{_DOMAIN_LABELS.get(d, d)} ({len(grouped[d])})"
        selected = _category_picker(options, labels)

        # Render sections.
        domains = domains_present if selected == "All" else [selected]
        for domain in domains:
            items = grouped.get(domain)
            if not items:
                continue
            _category_header(domain, len(items), len(jobs))
            for job in items:
                _render_job(job)


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
                    st.success(f"Status updated to {new_status}")
    else:
        st.info("No applications found. Apply to jobs from the Jobs page!")


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
                        with st.expander(
                            f"{color} **{m.get('job_title', 'N/A')}** at {m.get('company', 'N/A')} — Match: {score or 0}%"
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
    st.markdown(
        "Control your **daily job alert** (sent every day to your email and "
        "Telegram). Pick which **categories** to receive — e.g. select "
        "*🔐 Cybersecurity* to get only security jobs with their apply links."
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
