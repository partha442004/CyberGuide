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

try:
    from dashboard.invite import (
        DEFAULT_DASHBOARD_URL,
        build_invite_link,
        count_referrals,
        invite_caption,
        parse_invite_params,
        referral_leaderboard,
        referral_time_series,
        team_domain_split,
        team_growth_stats,
        team_rows,
    )
except ImportError:  # pragma: no cover - older deployment without invite.py
    from urllib.parse import quote as _quote

    DEFAULT_DASHBOARD_URL = "https://cyberguide2026aug.streamlit.app/"

    def build_invite_link(**kwargs) -> str:  # type: ignore[no-untyped-def]
        """Fallback link builder (no domain validation) for old deployments."""
        params = []
        if kwargs.get("email"):
            params.append(f"invite={_quote(str(kwargs['email']).strip())}")
        if kwargs.get("name"):
            params.append(f"ref={_quote(str(kwargs['name']).strip())}")
        if kwargs.get("location"):
            params.append(f"loc={_quote(str(kwargs['location']).strip())}")
        url = str(kwargs.get("base_url") or DEFAULT_DASHBOARD_URL).rstrip("/") + "/"
        return url + ("?" + "&".join(params) if params else "")

    def parse_invite_params(raw: dict) -> dict:  # noqa: ARG001
        """No invite support on old deployments."""
        return {}

    def invite_caption(invite: dict) -> str | None:  # noqa: ARG001
        """No invite support on old deployments."""
        return None

    def count_referrals(users: list, referrer_email: str | None) -> int:  # noqa: ARG001
        """No referral support on old deployments."""
        return 0

    def referral_leaderboard(users: list, limit: int = 5) -> list:  # noqa: ARG001
        """No leaderboard on old deployments."""
        return []

    def referral_time_series(users: list, referrer_email: str | None) -> list:  # noqa: ARG001
        """No referral analytics on old deployments."""
        return []

    def team_growth_stats(users: list, me_email: str | None = None) -> dict:  # noqa: ARG001
        """No growth stats on old deployments."""
        return {
            "team_size": 0,
            "joined_recently": 0,
            "my_referrals": 0,
            "referrals_recently": 0,
        }

    def team_domain_split(users: list) -> list:  # noqa: ARG001
        """No domain split on old deployments."""
        return []

    def team_rows(users: list, me_email: str | None = None) -> list:  # noqa: ARG001
        """No team view on old deployments."""
        return []


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
        "frontend",
        (
            "frontend",
            "front-end",
            "front end",
            "react",
            "angular",
            "vue",
            "ui developer",
            "ui engineer",
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
            "full stack",
            "fullstack",
            "devops",
            "sre",
            "python",
            "javascript",
            "typescript",
            "java",
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
    "frontend": "🖥️ Frontend / UI",
    "coding": "💻 Coding / Software",
    "data": "📊 Data & Analytics",
    "design": "🎨 Design",
    "finance": "💰 Finance / Admin",
    "marketing": "📣 Marketing / Sales",
    "other": "📦 Other",
}

_DOMAIN_ORDER = [
    "security",
    "frontend",
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
    "frontend": {
        "color": "#06b6d4",
        "grad": "linear-gradient(135deg,#22d3ee,#0e7490)",
        "icon": "🖥️",
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
        if method == "DELETE":
            return httpx.delete(url, timeout=timeout)
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


def _telegram_finder_block(chat_id: str | None = None, auto_save: bool = False) -> None:
    """Render the 'find my Telegram chat ID' helper (Settings + register).

    Calls the API's ``GET /notifications/telegram/chat-id`` to look up the
    newest chat that messaged the bot. On the register tab (``auto_save``
    False) the found chat ID is stored in session state so the form can
    pre-fill it; on the Settings page (``auto_save`` True) it is written
    straight to the signed-in user's profile via ``PUT /users/{id}``.
    ``chat_id`` is the current value (if any) shown as already-known.
    """
    st.markdown(
        "**📱 Don't know your Telegram chat ID?** Message the bot once "
        "(e.g. `/start`) — and make sure *you* are the last person to message "
        "it — then click below and we'll find it for you."
    )
    if chat_id:
        st.caption(f"Current chat ID: `{chat_id}`")
    if st.button(
        "🔎 Find my Telegram chat ID",
        key=f"find_tg_{chat_id or 'none'}_{st.session_state.get('tg_find_n', 0)}",
    ):
        st.session_state["tg_find_n"] = st.session_state.get("tg_find_n", 0) + 1
        found = fetch_data("/notifications/telegram/chat-id")
        if found and found.get("chat_id"):
            cid = found["chat_id"]
            if auto_save:
                saved = _api(
                    f"/users/{_current_user_id()}",
                    method="PUT",
                    json_data={"telegram_chat_id": cid},
                    timeout=15,
                )
                if saved:
                    st.success(
                        f"✅ Found your chat ID: `{cid}` — saved to your account! "
                        "Your alerts now reach your own Telegram."
                    )
                else:
                    st.error(
                        f"✅ Found your chat ID: `{cid}`, but saving it failed — "
                        "paste it in My Account → Telegram chat ID."
                    )
            else:
                st.success(
                    f"✅ Found your chat ID: `{cid}` — it's filled in below, just save."
                )
                st.session_state["found_telegram_chat_id"] = cid
        else:
            hint = (found or {}).get("hint") or "Nothing found yet."
            st.warning(f"{hint} Then press the button again.")


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


def _render_job(job: dict, match: Any = None) -> None:
    """One job as a clean, hoverable card with real widgets.

    All scraped fields (title, company, location, description, ...) are
    untrusted external content, so every value interpolated into HTML is
    escaped before rendering with ``unsafe_allow_html``. When ``match`` is
    given (a match dict from ``/resumes/match-batch``, or a legacy plain
    score float), a colored match chip is shown on the card; dicts also
    render the full matched / related / missing-skill breakdown below it.
    """
    title = escape(str(job.get("title", "Untitled")))
    company = escape(str(job.get("company", "Unknown")))
    posted = job.get("posted_at")

    match_score = match.get("match_score") if isinstance(match, dict) else match

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
                if isinstance(match, dict):
                    _match_breakdown(match)

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
            _ic1, _ic2 = st.columns(2)
            with _ic1:
                if st.button(
                    "📌 Save",
                    key=f"save_{job.get('id', title)}",
                    use_container_width=True,
                    help="Bookmark this job (also boosts its 🔥 rank).",
                ):
                    _toggle_bookmark(job)
            with _ic2:
                if st.button(
                    "👁 Seen",
                    key=f"view_{job.get('id', title)}",
                    use_container_width=True,
                    help="Counts as a view — feeds the 🔥 Trending ranking.",
                ):
                    _api(f"/jobs/{str(job.get('id'))}/view", method="POST", timeout=15)
            _apply_popover = getattr(st, "popover", None)
            if _apply_popover is not None:
                with _apply_popover("📋 Apply"):
                    _apply_status = st.radio(
                        "Status when applied",
                        ["applied", "interview", "offer"],
                        horizontal=True,
                        key=f"apply_status_{job.get('id', title)}",
                    )
                    if st.button("Confirm", key=f"apply_go_{job.get('id', title)}"):
                        _track_application(job.get("id"), title, _apply_status)
            elif st.button(
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


def _track_application(job_id: Any, title: str, status: str | None = None) -> None:
    """Create an application for the current user via the real API.

    When ``status`` is given (from the Apply popover), the application is
    created and immediately updated to that status (applied / interview /
    offer) so tracking is a single action.
    """
    user_id = _current_user_id()
    resp = _api_raw(
        "/applications/",
        method="POST",
        json_data={"job_id": str(job_id), "user_id": user_id},
        timeout=20,
    )
    if resp is not None and resp.status_code in (200, 201):
        app_id = (resp.json() or {}).get("id")
        status_ok = True
        if status and app_id:
            put_resp = _api_raw(
                f"/applications/{app_id}",
                method="PUT",
                json_data={"status": status},
                timeout=15,
            )
            status_ok = put_resp is not None and put_resp.status_code in (200, 201)
        # ``title`` is already escaped by _render_job before being passed in.
        st.success(
            f"✅ Application tracked for **{title}**"
            + (f" as **{status}**" if status and status_ok else "")
            + "! Update it anytime on the Applications page."
        )
    elif resp is not None and resp.status_code == 422:
        st.error("Couldn't track the application — the job may not be saved yet.")
    else:
        st.error("Applications API unreachable. Is the API server running?")


@st.cache_data(ttl=60, show_spinner=False)
def _bookmarks_payload() -> list:
    """Bookmark list from the API (cached 60s so toggles refresh fast).

    Cached so ``_bookmarks_payload.clear()`` can invalidate it after a
    toggle; ``_bookmarked_job_ids`` derives the save/unsave decision from
    it.
    """
    data = fetch_data("/bookmarks/?limit=200") or {}
    return list(data.get("bookmarks") or [])


def _bookmarked_job_ids() -> dict[str, str]:
    """Map job id -> bookmark id for ``item_type='job'`` bookmarks."""
    return {
        str(b.get("item_id")): str(b.get("id"))
        for b in _bookmarks_payload()
        if b.get("item_type") == "job"
    }


def _clear_bookmark_cache() -> None:
    """Drop the cached bookmark list after a toggle."""
    _bookmarks_payload.clear()


def _toggle_bookmark(job: dict) -> None:
    """Save / unsave a job via the bookmarks API (one-click toggle).

    The API 409s on duplicates, so the button flips between POST (save)
    and DELETE (unsave) based on the session-cached bookmark set. Saved
    jobs also gain bookmark weight in the 🔥 Trending ranking.
    """
    job_id = str(job.get("id") or "")
    title = str(job.get("title") or "Untitled")
    if not job_id:
        st.error("Cannot save — job id missing.")
        return
    saved = _bookmarked_job_ids()
    if job_id in saved:
        resp = _api_raw(f"/bookmarks/{saved[job_id]}", method="DELETE", timeout=15)
        if resp is not None and resp.status_code in (200, 204):
            st.success(f"Removed **{escape(title)}** from saved jobs.")
            _clear_bookmark_cache()
        else:
            st.error("Couldn't unsave — bookmarks API unreachable.")
    else:
        resp = _api_raw(
            "/bookmarks/",
            method="POST",
            json_data={"item_type": "job", "item_id": job_id},
            timeout=15,
        )
        _clear_bookmark_cache()
        if resp is not None and resp.status_code in (200, 201):
            st.success(f"📌 Saved **{escape(title)}** — see the Bookmarks page.")
        elif resp is not None and resp.status_code == 409:
            st.caption("Already saved.")
        else:
            st.error("Couldn't save — bookmarks API unreachable.")


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


_STATUS_LABELS = {
    "saved": "📌 Saved",
    "applied": "📨 Applied",
    "assessment": "🧪 Assessment",
    "interview": "🗓 Interview",
    "offer": "🎉 Offer",
    "rejected": "🚫 Rejected",
    "joined": "🎊 Joined",
}


def _save_application_notes(app_id: str, notes: str) -> None:
    """Persist application notes via the real API (PUT with ``notes``)."""
    resp = _api_raw(
        f"/applications/{app_id}",
        method="PUT",
        json_data={"notes": notes.strip()},
        timeout=20,
    )
    if resp is not None and resp.status_code == 200:
        st.success("✅ Notes saved")
    else:
        st.error("Could not save notes — is the API server running?")


def _set_application_priority(app_id: str, priority: int) -> None:
    """Persist an application's ⭐ priority via the real API (PUT)."""
    resp = _api_raw(
        f"/applications/{app_id}",
        method="PUT",
        json_data={"priority": priority},
        timeout=20,
    )
    if resp is not None and resp.status_code == 200:
        st.success("⭐ Priority updated" if priority else "⭐ Priority cleared")
        # Rerun so the ⭐ Priority applications panel reflects the change now.
        st.rerun()
    else:
        st.error("Could not update priority — is the API server running?")


def _login_user(profile: dict) -> None:
    """Store a user profile in the Streamlit session."""
    st.session_state["user"] = profile


def _logout_user() -> None:
    """Clear the logged-in user from the session."""
    st.session_state.pop("user", None)


def _invite_params() -> dict:
    """Read + validate invite query params (``?invite=&ref=&domains=&loc=``).

    Works on current Streamlit (``st.query_params``) with a fallback to the
    older ``st.experimental_get_query_params`` so a friend opening an invite
    link always lands on a pre-filled signup form.
    """
    qp = getattr(st, "query_params", None)
    if qp is None:
        with suppress(Exception):
            qp = st.experimental_get_query_params()
        if qp is None:
            return {}
    try:
        raw = {key: qp[key] for key in qp}
    except Exception:
        return {}
    return parse_invite_params(raw)


def _match_jobs_to_resume(jobs: list, user_id: str) -> Any:
    """POST jobs to ``/resumes/match-batch`` — returns the raw result or None.

    Shared by the Saved Jobs tab and the My Matches page so the query-string
    construction and cap can never drift between the two.
    """
    job_ids = [j.get("id") for j in jobs if j.get("id")][:50]
    if not job_ids:
        return None
    return _api(
        f"/resumes/match-batch?user_id={user_id}&job_ids=" + "&job_ids=".join(job_ids),
        method="POST",
        timeout=45,
    )


def _my_top_matches(user_id: str, limit: int = 8) -> list[tuple[dict, float, dict]]:
    """Best resume matches for a user against the newest jobs, score > 0.

    Returns ``[(job, score, match)]`` sorted by score desc — ``match``
    carries the breakdown the API already computes (matched / related /
    missing skills, ATS compatibility, suggestions) so the UI can explain
    the percentage instead of showing a bare number. Empty when the user
    has no resume yet or the API is unreachable.
    """
    jobs = fetch_data("/jobs/?limit=50") or {}
    job_list = jobs.get("jobs") or []
    result = _match_jobs_to_resume(job_list, user_id)
    if not result or not result.get("matches"):
        return []
    by_id = {str(j.get("id")): j for j in job_list}
    scored: list[tuple[dict, float, dict]] = []
    for match in result["matches"]:
        score = match.get("match_score")
        job = by_id.get(str(match.get("job_id")))
        if job and isinstance(score, (int, float)) and score > 0:
            scored.append((job, float(score), match))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def _match_breakdown(match: dict) -> None:
    """Render the 'why this score' breakdown for one match payload.

    Color-coded chips: ✅ matched skills (green), 🔄 transferable/related
    skills (blue), ⬜ missing skills (red), plus the ATS compatibility %
    and the first suggestion. ``unsafe_allow_html`` is safe here because
    every value is passed through ``escape`` before interpolation.
    """
    matched = [s for s in (match.get("matched_skills") or []) if s]
    related = [s for s in (match.get("related_skills") or []) if s]
    missing = [s for s in (match.get("missing_skills") or []) if s]

    def chips(items: list, icon: str, style: str) -> str:
        return "".join(
            f'<span class="chip" style="{style}">{icon} {escape(str(s))}</span>'
            for s in items[:6]
        )

    rows: list[str] = []
    if matched:
        rows.append(
            '<div class="chip-row">'
            + chips(matched, "✅", "color:#059669;border-color:rgba(5,150,105,0.35);")
            + "</div>"
        )
    if related:
        rows.append(
            '<div class="chip-row">'
            + chips(related, "🔄", "color:#2563eb;border-color:rgba(37,99,235,0.35);")
            + "</div>"
        )
    if missing:
        rows.append(
            '<div class="chip-row">'
            + chips(missing, "⬜", "color:#dc2626;border-color:rgba(220,38,38,0.35);")
            + "</div>"
        )
    if rows:
        st.markdown("".join(rows), unsafe_allow_html=True)
    ats = match.get("ats_score")
    if ats is not None:
        st.caption(f"📄 ATS compatibility: {float(ats):.0f}%")
    suggestions = [s for s in (match.get("suggestions") or []) if s]
    if suggestions:
        st.caption("💡 " + escape(str(suggestions[0])))


def _cover_letter_block(job_id: str, company: str) -> None:
    """'Generate cover letter' button + copyable letter for one job.

    Calls the API's ``POST /resumes/cover-letter`` (rule-based, no API
    key) and shows the letter in a read-only text area with a Copy
    button. Fails silently into an info note when the API is unreachable
    or the user has no resume yet.
    """
    user_id = _current_user_id()
    btn_key = f"cl_btn_{job_id}"
    if st.button("✍️ Generate cover letter", key=btn_key, use_container_width=True):
        result = _api(
            f"/resumes/cover-letter?user_id={user_id}&job_id={job_id}",
            method="POST",
            timeout=30,
        )
        if not result or not result.get("cover_letter"):
            st.info(
                "Cover letter unavailable — upload your resume on the "
                "Resume Match page first, then try again."
            )
            return
        letter = result["cover_letter"]
        with st.expander("📄 Your tailored cover letter", expanded=True):
            st.text_area(
                "Cover letter",
                value=letter,
                height=320,
                key=f"cl_area_{job_id}",
            )
            st.download_button(
                "📥 Download .txt",
                data=letter.encode("utf-8"),
                file_name=f"cover-letter-{company or 'job'}.txt".replace(
                    " ", "-"
                ).lower(),
                mime="text/plain",
                key=f"cl_dl_{job_id}",
            )


def _interview_prep_block(job_id: str, company: str) -> None:
    """'Generate interview questions' button + prep list for one job.

    Calls the API's ``POST /resumes/interview-prep`` (rule-based, no API
    key) and shows the grouped question list plus prep tips. Fails
    silently into an info note when the API is unreachable or the user
    has no resume yet.
    """
    user_id = _current_user_id()
    btn_key = f"ip_btn_{job_id}"
    if st.button("🎤 Interview prep", key=btn_key, use_container_width=True):
        result = _api(
            f"/resumes/interview-prep?user_id={user_id}&job_id={job_id}",
            method="POST",
            timeout=30,
        )
        if not result or not result.get("questions"):
            st.info(
                "Interview prep unavailable — upload your resume on the "
                "Resume Match page first, then try again."
            )
            return
        questions = result["questions"]
        tips = result.get("tips") or []
        _cat_emoji = {
            "role": "🎯",
            "technical": "🧠",
            "behavioral": "🗣️",
            "gap": "📌",
            "company": "🏢",
        }
        with st.expander("🎤 Your interview prep list", expanded=True):
            for q in questions:
                cat = q.get("category", "")
                st.markdown(
                    f"**{_cat_emoji.get(cat, '❓')} {escape(str(q.get('question', '')))}**"
                )
                if cat:
                    st.caption(f"{cat} · {escape(company or 'job')}")
            if tips:
                st.markdown("**💡 Prep tips**")
                for tip in tips:
                    st.write(f"• {escape(tip)}")
            if result.get("match_score") is not None:
                st.caption(f"📊 Match score: {result['match_score']:.0f}%")


@st.cache_data(ttl=60, show_spinner=False)
def _team_members() -> list:
    """Registered user profiles (cached 60s so a new member shows up fast)."""
    data = fetch_data("/users") or {}
    return list(data.get("users") or [])


def _team_count() -> int:
    """Number of registered accounts."""
    return len(_team_members())


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

        # ── Invite a friend (multi-user growth) ────────────────────────
        st.divider()
        st.subheader("🤝 Invite a friend")
        st.markdown(
            "Send your friend a **personalized signup link** — their form is "
            "pre-filled with your categories and location. Each person gets "
            "their own daily alerts in *their* domain, sent to *their* email / "
            "Telegram."
        )
        invite_url = build_invite_link(
            base_url=_get_setting("DASHBOARD_URL", DEFAULT_DASHBOARD_URL),
            email=user.get("email"),
            name=user.get("name"),
            domains=user.get("domains") or [],
            location=user.get("location") or None,
        )
        st.text_input("Share this invite link", value=invite_url)
        st.caption(
            "When they open it → Create account → their preferred categories "
            "and city are already filled in."
        )
        members = _team_members()
        if members:
            st.caption(
                f"👥 **{len(members)} account(s)** already getting personalized "
                "alerts on this platform."
            )

        # Referral count — how many friends joined through *this* account's link.
        referrals = count_referrals(members, user.get("email"))
        if referrals:
            st.success(
                f"🎁 **{referrals} friend(s)** signed up through your invite link!"
            )
        else:
            st.caption(
                "🎁 Share your link above — when a friend signs up through it, "
                "it's counted right here."
            )

        # Team growth panel — who joined, and who invited the most.
        growth = team_growth_stats(members, user.get("email"))
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.metric("👥 Team", growth["team_size"])
        with g2:
            st.metric("🆕 Joined (7d)", growth["joined_recently"])
        with g3:
            st.metric("🎁 Your referrals", growth["my_referrals"])
        with g4:
            st.metric("🎁 Referred (7d)", growth["referrals_recently"])

        board = referral_leaderboard(members)
        if board:
            st.markdown("**🏆 Top inviters**")
            medals = ["🥇", "🥈", "🥉"]
            my_email = (user.get("email") or "").lower()
            for i, row in enumerate(board):
                medal = medals[i] if i < len(medals) else f"{i + 1}."
                is_me = row["email"].lower() == my_email
                suffix = " (you)" if is_me else ""
                st.caption(
                    f"{medal} {escape(row['name'])}{suffix} — "
                    f"{row['count']} referral(s)"
                )

        # Per-domain team split — which categories your team picked.
        split = team_domain_split(members)
        if split:
            st.markdown("**🏷 Team by category**")
            split_chips = "".join(
                f'<span class="chip">{_DOMAIN_LABELS.get(r["domain"], r["domain"])}: '
                f"{r['count']}</span>"
                for r in split
            )
            st.markdown(
                f'<div class="chip-row">{split_chips}</div>',
                unsafe_allow_html=True,
            )

        # Referral growth chart — your invites per month (last 6 months).
        series = referral_time_series(members, user.get("email"))
        if any(r["count"] > 0 for r in series):
            st.markdown("**📈 Referrals per month**")
            import pandas as pd

            df = pd.DataFrame(series)
            fig = px.bar(
                df,
                x="month",
                y="count",
                labels={"month": "Month", "count": "Referrals"},
                color_discrete_sequence=["#667eea"],
            )
            st.plotly_chart(fig, use_container_width=True)

        # Team directory — who is on the platform.
        st.subheader("🌍 Team directory")
        rows = team_rows(members, me_email=user.get("email"))
        if rows:
            for row in rows[:20]:
                badges = []
                if row["is_me"]:
                    badges.append('<span class="chip">👤 You</span>')
                if row["referred_by_me"]:
                    badges.append('<span class="chip">🎁 via your link</span>')
                domain_labels = (
                    ", ".join(_DOMAIN_LABELS.get(d, d) for d in row["domains"])
                    or "All categories"
                )
                st.markdown(
                    f"**{escape(row['name'])}** "
                    f"<span style='opacity:0.6'>{escape(row['email'])}</span> "
                    f"<span style='opacity:0.6'>· {escape(row['location'])}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"🏷 {escape(domain_labels)}")
                if badges:
                    st.markdown(
                        '<div class="chip-row">' + "".join(badges) + "</div>",
                        unsafe_allow_html=True,
                    )
                st.divider()
        else:
            st.caption("No members yet — be the first to invite someone!")

        # ── Danger zone: self-service account deletion ────────────────
        st.divider()
        st.subheader("🗑 Delete my account")
        st.caption(
            "Permanently removes your profile, applications, alert history, "
            "watchlists and resume. **This cannot be undone.**"
        )
        confirm = st.checkbox("I understand — delete everything permanently")
        if st.button(
            "Delete my account",
            disabled=not confirm,
            use_container_width=True,
        ):
            resp = _api_raw(f"/users/{user.get('id')}", method="DELETE", timeout=30)
            if resp is not None and resp.status_code in (200, 204, 404):
                # 404 = the account is already gone (e.g. deleted elsewhere).
                st.session_state["account_deleted"] = True
                _logout_user()
                st.rerun()
            elif resp is None:
                st.error("Could not reach the API — is it running?")
            else:
                st.error("The API refused the deletion — please try again.")

        if st.button("🚪 Log out", use_container_width=True):
            _logout_user()
            st.rerun()
        return

    # A just-deleted account lands here (signed out) with a visible goodbye.
    if st.session_state.pop("account_deleted", False):
        st.success("Your account and all its data were deleted. Sorry to see you go!")

    # ── Not signed in: register or log in ─────────────────────────────
    st.markdown(
        "Create a free account to get **personalized job alerts** — your own "
        "categories, your own resume match %, and delivery to *your* email / "
        "Telegram. Login is by email only (no password)."
    )
    tab_register, tab_login = st.tabs(["✨ Create account", "🔑 Log in"])

    with tab_register:
        _invite = _invite_params()
        _invite_caption = invite_caption(_invite)
        if _invite_caption:
            st.info(_invite_caption)
        _telegram_finder_block()
        with st.form("register_form"):
            name = st.text_input("Full name *")
            email = st.text_input("Email *")
            location = st.text_input(
                "Location",
                value=_invite.get("location", ""),
                placeholder="e.g. Bengaluru, India",
            )
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
                value=st.session_state.pop("found_telegram_chat_id", ""),
                help="Message @userinfobot on Telegram to see your chat ID — "
                "alerts then reach *your* Telegram instead of the shared chat. "
                "Tip: use the 'Find my Telegram chat ID' button above.",
            )
            phone_number = st.text_input(
                "Phone number for SMS alerts (optional)",
                placeholder="+919876543210",
                help="Include the country code (e.g. +91 for India) — your "
                "daily digest can also arrive by SMS.",
            )
            default_domains = _invite.get("domains", ["security"])
            domains = _category_picker_multi("🏷 Preferred categories", default_domains)
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
                "phone_number": phone_number.strip() or None,
                "domains": [] if "all" in domains else domains,
                "skills": [s.strip() for s in skills.split(",") if s.strip()],
                "referred_by": _invite.get("invite") or None,
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
# Page: Team & Users (admin onboarding — add friends with role + location)
# ---------------------------------------------------------------------------


def show_team() -> None:
    """Admin page to onboard new members with their own role + city.

    Every account gets personalized daily alerts: the admin picks the
    friend's categories (role/domain) and location, the API auto-enables
    alerts, and the access token shown once lets the friend log in. Also
    lists the whole team with per-member alert toggles and removal.
    """
    st.header("👥 Team & Users")
    st.markdown(
        "Add a friend and they'll get **their own daily alerts** in *their* "
        "role + city — sent to *their* email / Telegram, never mixed with yours. "
        "You pick the categories (e.g. Frontend, Cybersecurity) and the location "
        "(e.g. Chennai); they just log in with the token you share."
    )

    # ── Onboard a new member ─────────────────────────────────────────
    st.subheader("➕ Add a new member")
    with st.form("admin_add_user_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full name *", key="team_name")
        with c2:
            email = st.text_input("Email *", key="team_email")
        c3, c4 = st.columns(2)
        with c3:
            location = st.text_input(
                "Location *",
                key="team_location",
                placeholder="e.g. Chennai",
                help="Their digest is scoped to this city — your alerts stay separate.",
            )
        with c4:
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
                key="team_exp",
            )
        domains = _category_picker_multi(
            "🏷 Their role / categories",
            ["security"],
        )
        skills = st.text_input(
            "Skills (comma-separated, optional)",
            key="team_skills",
            placeholder="e.g. react, redux, typescript",
        )
        c5, c6 = st.columns(2)
        with c5:
            telegram_chat_id = st.text_input(
                "Telegram chat ID (optional)",
                key="team_tg",
                help="Alerts also reach their Telegram — ask them to message the "
                "bot once and paste the chat ID here.",
            )
        with c6:
            phone_number = st.text_input(
                "Phone for SMS (optional)",
                key="team_phone",
                placeholder="+919876543210",
            )
        resume_file = st.file_uploader(
            "Upload their resume (PDF) — optional, turns on match % instantly",
            type=["pdf"],
            key="team_resume",
            help="Parsed right after the account is created, so their job "
            "match % works from day one.",
        )
        submitted = st.form_submit_button(
            "🚀 Create account + turn on alerts", type="primary"
        )

    if submitted:
        if not name.strip() or "@" not in email or not location.strip():
            st.error("Please fill in the name, a valid email and the location.")
        else:
            payload = {
                "name": name.strip(),
                "email": email.strip(),
                "location": location.strip(),
                "experience_level": experience or None,
                "telegram_chat_id": telegram_chat_id.strip() or None,
                "phone_number": phone_number.strip() or None,
                "domains": [] if "all" in domains else domains,
                "skills": [s.strip() for s in skills.split(",") if s.strip()],
                "referred_by": (_current_user() or {}).get("email"),
            }
            resp = _api_raw(
                "/users/register", method="POST", json_data=payload, timeout=30
            )
            if resp is None:
                st.error("Could not reach the API — is it running?")
            elif resp.status_code in (200, 201):
                profile = resp.json()
                st.success(
                    f"✅ {profile.get('name')} is on the platform — personalized "
                    "alerts are ON."
                )
                st.markdown(
                    "**🔑 Share this token with them** (they log in with it — "
                    "it is shown only once):"
                )
                st.code(profile.get("access_token", ""), language=None)
                domain_txt = ", ".join(
                    _DOMAIN_LABELS.get(d, d) for d in profile.get("domains") or []
                )
                st.caption(
                    f"📍 {profile.get('location')} · 🏷 {domain_txt or 'All categories'} · "
                    "the daily digest goes out at 8:00 / 13:00 / 19:00 IST."
                )
                if resume_file is not None and profile.get("id"):
                    with st.spinner("Parsing their resume..."):
                        files = {
                            "file": (
                                resume_file.name,
                                resume_file.getvalue(),
                                "application/pdf",
                            )
                        }
                        up = _api(
                            f"/resumes/upload?user_id={profile.get('id')}",
                            method="POST",
                            files=files,
                            timeout=30,
                        )
                        if up:
                            st.success("📄 Resume parsed — their match % is live.")
                        else:
                            st.warning(
                                "Account created, but the resume could not be "
                                "parsed — they can upload it later on the "
                                "Resume Match page."
                            )
            else:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                st.error(f"Could not create the account: {detail}")

    # ── Team directory with alert toggles ────────────────────────────
    st.divider()
    st.subheader("🗂 Team directory")
    members = _team_members()
    if not members:
        st.caption("No members yet — add the first one above.")
        return

    st.caption(
        f"**{len(members)} account(s)** · click a toggle to pause/resume that "
        "person's daily alerts (vacation mode)."
    )
    for row in members:
        uid = row.get("id")
        domain_txt = (
            ", ".join(_DOMAIN_LABELS.get(d, d) for d in row.get("domains") or [])
            or "All categories"
        )
        is_me = uid == _current_user_id()
        col_name, col_alerts, col_actions = st.columns([3, 1, 1])
        with col_name:
            label = escape(row.get("name") or "")
            if is_me:
                label += " (you)"
            st.markdown(
                f"**{label}** "
                f"<span style='opacity:0.6'>{escape(row.get('email') or '')}</span> · "
                f"<span style='opacity:0.6'>📍 {escape(row.get('location') or '—')}</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"🏷 {escape(domain_txt)}")
        if is_me:
            with col_alerts:
                st.caption("—")
            with col_actions:
                st.caption("—")
            continue
        with col_alerts:
            key = f"alerts_{uid}"
            prefs = _api(f"/notifications/preferences/{uid}", timeout=15) or {}
            is_enabled = bool(prefs.get("is_enabled", True))
            toggled = st.toggle(
                "Alerts", value=is_enabled, key=key, label_visibility="collapsed"
            )
            if toggled != is_enabled:
                saved = _api(
                    f"/notifications/preferences/{uid}",
                    method="PUT",
                    json_data={"is_enabled": toggled},
                    timeout=15,
                )
                if saved:
                    st.caption("✅ saved")
                    st.session_state.pop(key, None)
                else:
                    st.error("Save failed")
        with col_actions:
            if st.button(
                "🔔 Test alert",
                key=f"tst_{uid}",
                use_container_width=True,
                help="Send a test alert to this member's own email/Telegram "
                "right now — no waiting for the next digest slot.",
            ):
                with st.spinner("Sending test alert..."):
                    resp = _api_raw(
                        f"/notifications/user/{uid}/test",
                        method="POST",
                        json_data={},
                        timeout=30,
                    )
                if resp is None:
                    st.error("Could not reach the API — is it running?")
                else:
                    try:
                        data = resp.json()
                    except Exception:
                        data = {}
                    if data.get("sent"):
                        st.success(f"✅ {data.get('hint') or 'Test alert sent.'}")
                    else:
                        st.warning(f"{data.get('hint') or 'Nothing was sent.'}")
            if st.button("🗑 Remove", key=f"rm_{uid}", use_container_width=True):
                resp = _api_raw(f"/users/{uid}", method="DELETE", timeout=30)
                if resp is not None and resp.status_code in (200, 204, 404):
                    st.success(f"Removed {row.get('name')} and their data.")
                    _team_members.clear()
                    st.rerun()
                else:
                    st.error("Could not remove the member.")
        st.divider()


# ---------------------------------------------------------------------------
# Page: My Matches (personal stats)
# ---------------------------------------------------------------------------


def show_my_matches() -> None:
    """Personal match center: top matches, pipeline stats, alert history.

    Everything here is scoped to the signed-in user (or the legacy ``user1``
    default when browsing signed-out), so each friend sees only their own
    numbers.
    """
    st.header("🎯 My Matches")
    user_id = _current_user_id()
    user = _current_user()

    if user:
        st.caption(
            f"Personal stats for **{escape(user.get('name', ''))}** — "
            f"{escape(user.get('email', ''))}"
        )
    else:
        st.caption(
            "Browsing as **user1** (legacy account) — create your own account "
            "on My Account to get personalized numbers."
        )

    # ── Top-line metrics ──────────────────────────────────────────────
    history = fetch_data(f"/notifications/preferences/{user_id}/history?limit=20") or {}
    sends = history.get("history") or []
    apps = fetch_data(f"/applications/?user_id={user_id}&limit=200") or {}
    app_list = apps.get("applications") or []
    matches = _my_top_matches(user_id)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📬 Alerts sent to me", len(sends))
    with col2:
        st.metric("📋 Applications tracked", len(app_list))
    with col3:
        st.metric("🎯 Best match now", f"{matches[0][1]:.0f}%" if matches else "—")

    # ── Top matches ───────────────────────────────────────────────────
    st.subheader("🏆 Your best matches right now")
    if matches:
        for job, score, match in matches:
            title = str(job.get("title") or "Untitled role")
            company = str(job.get("company") or "Unknown")
            color = (
                "#059669" if score >= 70 else ("#d97706" if score >= 40 else "#dc2626")
            )
            st.markdown(
                f"**{escape(title)}**",
            )
            st.markdown(
                '<div class="chip-row">'
                f'<span class="chip" style="color:{color};background:rgba(5,150,105,0.08);'
                f'border-color:rgba(5,150,105,0.25);font-weight:700;">🎯 {score:.0f}%</span>'
                f'<span class="chip">🏢 {escape(company)}</span>'
                f'<span class="chip">📍 {escape(str(job.get("location") or "Remote"))}</span>'
                "</div>",
                unsafe_allow_html=True,
            )
            _match_breakdown(match)
            if job.get("url"):
                st.link_button("🔗 View", job["url"], key=f"mm_{job.get('id')}")
            _cover_letter_block(str(job.get("id") or ""), company)
            _interview_prep_block(str(job.get("id") or ""), company)

            st.divider()
    else:
        st.info(
            "No match scores yet — upload your resume on the **Resume Match** "
            "page, then come back here for your personal top picks."
        )

    # ── Application pipeline ──────────────────────────────────────────
    st.subheader("📋 Your application pipeline")
    if app_list:
        counts: dict[str, int] = {}
        for a in app_list:
            status = str(a.get("status") or "saved")
            counts[status] = counts.get(status, 0) + 1
        chips = "".join(
            f'<span class="chip">{escape(s)}: {c}</span>' for s, c in counts.items()
        )
        st.markdown(f'<div class="chip-row">{chips}</div>', unsafe_allow_html=True)
    else:
        st.caption(
            "No applications yet — hit **Apply** on any job card to start tracking."
        )

    # ── Alert history timeline ────────────────────────────────────────
    st.subheader("📬 Your alert history")
    if sends:
        for row in sends:
            channels = row.get("channels") or []
            results = row.get("results") or {}
            status_icons = "".join("✅" if results.get(c) else "❌" for c in channels)
            status_icons = status_icons or "—"
            domains_txt = ", ".join(row.get("domains") or []) or "all categories"
            sent_jobs = row.get("jobs") or []
            with st.expander(
                f"📬 **{escape(str(row.get('subject') or 'Alert'))}** — "
                f"{row.get('job_count') or 0} job(s) · {_time_ago(row.get('sent_at'))}"
            ):
                st.caption(f"🏷 {escape(domains_txt)} · channels {status_icons}")
                if sent_jobs:
                    for jj_i, jj in enumerate(sent_jobs):
                        jj_title = escape(str(jj.get("title") or "Untitled role"))
                        jj_company = escape(str(jj.get("company") or "Unknown"))
                        jj_loc = escape(str(jj.get("location") or "Remote"))
                        jj_score = jj.get("match_score")
                        score_txt = (
                            f" · 🎯 {jj_score:.0f}%"
                            if isinstance(jj_score, (int, float))
                            else ""
                        )
                        jj_line = (
                            f"**{jj_title}**{score_txt} — {jj_company} · 📍 {jj_loc}"
                        )
                        st.markdown(jj_line)
                        jj_url = jj.get("url")
                        if jj_url:
                            st.link_button(
                                "🔗 View",
                                jj_url,
                                key=f"hist_{row.get('id')}_{jj_i}_{jj.get('title')}",
                            )
                        st.divider()
                else:
                    st.caption(
                        "Job details weren't recorded for this send (older "
                        "digests predate job-level history)."
                    )
    else:
        st.caption(
            "No alert history yet — your first digest arrives at the next "
            "scheduled refresh (8:00 / 13:00 / 19:00 IST)."
        )


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
                "My Matches",
                "AI Tools",
                "Learning",
                "Settings",
                "My Account",
                "Team & Users",
            ],
        )
        st.divider()
        user = _current_user()
        if user:
            st.markdown(f"👤 **{user.get('name', '')}**")
            st.caption(f"Signed in · {user.get('email', '')}")
        else:
            st.caption("Not signed in — browsing as **user1**")
        with suppress(Exception):
            st.markdown(
                "<div style='margin-top:14px;font-size:0.8em;'>"
                "📲 <a href='/app' target='_blank' style='color:inherit;'>"
                "Install as an app</a> — opens the dashboard fullscreen on "
                "your phone.</div>",
                unsafe_allow_html=True,
            )

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
        "My Matches": show_my_matches,
        "AI Tools": show_ai_tools,
        "Learning": show_learning,
        "Settings": show_settings,
        "My Account": show_account,
        "Team & Users": show_team,
    }
    pages.get(page, show_overview)()


# ---------------------------------------------------------------------------
# Page: AI Tools (cover letter + interview questions + why I match)
# ---------------------------------------------------------------------------


def show_ai_tools() -> None:
    """One-click cover letter, interview questions and why-I-match per job."""
    st.header("🤖 AI Tools")
    st.markdown(
        "Pick any tracked job and generate a tailored **cover letter**, "
        "likely **interview questions** and a **why-I-match** breakdown — "
        "built from your resume skills + the job description."
    )

    jobs_data = fetch_data("/jobs/?limit=200")
    job_list = jobs_data.get("jobs") or []
    if not job_list:
        st.info("No jobs tracked yet — run a discovery search first.")
        return

    job_ids = [str(j.get("id", "")) for j in job_list]
    labels = [
        f"{j.get('title', 'Untitled')} @ {j.get('company', '?')} · "
        f"{j.get('location', '')}"
        for j in job_list
    ]
    selected = st.selectbox(
        "Choose a job", list(range(len(job_list))), format_func=lambda i: labels[i]
    )
    job = job_list[selected]
    st.markdown(
        f"**{escape(str(job.get('title', '')))}** — "
        f"{escape(str(job.get('company', '')))} · "
        f"{escape(str(job.get('location', '')))}"
    )

    if st.button("✨ Generate application kit", type="primary"):
        with st.spinner("Writing your kit…"):
            kit = _api(
                f"/ai/jobs/{job_ids[selected]}/apply-kit",
                method="POST",
                timeout=60,
            )
        if not kit:
            st.error("Could not generate the kit — the API may be busy. Try again.")
            return

        score = kit.get("match_score")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Match", f"{score:.0f}%" if score is not None else "—")
        with col2:
            st.metric("Matched skills", len(kit.get("matched_skills") or []))
        with col3:
            st.metric("Generated by", str(kit.get("generated_by", "template")).title())

        st.subheader("💡 Why I match")
        for line in kit.get("why_match") or []:
            st.markdown(f"- {line}")

        st.subheader("✍️ Cover letter")
        st.text_area(
            "Copy-ready cover letter",
            value=str(kit.get("cover_letter", "")),
            height=260,
        )
        if kit.get("cover_letter"):
            st.download_button(
                "⬇️ Download cover letter (.txt)",
                data=str(kit.get("cover_letter", "")),
                file_name="cover_letter.txt",
            )

        st.subheader("🎤 Likely interview questions")
        for i, q in enumerate(kit.get("interview_questions") or [], 1):
            st.markdown(f"{i}. {q}")

        with suppress(Exception):
            st.caption(
                "✨ Tip: a cover letter should be short and specific — "
                "replace [Your Name] and add 1–2 sentences from your own story."
            )


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------


def _domain_coverage_section() -> None:
    """Live per-category job counts so each user can see domain coverage.

    Answers the recurring "will I get jobs in my domain?" question: shows
    how many of the newest tracked jobs fall into each category (plus the
    fresh-24h count), and nudges when the signed-in user's preferred
    categories have nothing yet. Uses the same ``classify_domain`` the Saved
    Jobs tab uses so numbers never drift.
    """
    jobs_data = fetch_data("/jobs/?limit=300")
    job_list = jobs_data.get("jobs") or []
    if not job_list:
        return

    counts: dict[str, int] = {}
    fresh: dict[str, int] = {}
    for job in job_list:
        domain = classify_domain(job.get("title", ""))
        counts[domain] = counts.get(domain, 0) + 1
        if _is_fresh_24h(job.get("posted_at")):
            fresh[domain] = fresh.get(domain, 0) + 1

    st.markdown(
        '<div class="section-title">🗂 Domain coverage</div>'
        '<div class="section-sub">Live counts from the newest 300 tracked '
        "jobs — see at a glance which categories are well covered and which "
        "need a discovery run or imported links.</div>",
        unsafe_allow_html=True,
    )
    user = _current_user()
    prefs = (user or {}).get("domains") or []
    cols = st.columns(4)
    for i, domain in enumerate(_DOMAIN_ORDER):
        count = counts.get(domain, 0)
        fresh_n = fresh.get(domain, 0)
        style = _CATEGORY_STYLE.get(domain, _CATEGORY_STYLE["other"])
        label = _DOMAIN_LABELS.get(domain, domain)
        is_mine = domain in prefs
        with cols[i % 4]:
            st.markdown(
                f'<div class="stat-tile" style="border-top:4px solid '
                f'{style["color"]};">'
                f'<div class="stat-value">{count}</div>'
                f'<div class="stat-label">{escape(label)}</div>'
                f'<div style="font-size:0.74em;color:var(--muted);'
                f'margin-top:4px;">🆕 {fresh_n} new · 24h'
                + (" · 👤 your domain" if is_mine else "")
                + "</div></div>",
                unsafe_allow_html=True,
            )

    thin = [d for d in prefs if counts.get(d, 0) == 0]
    if thin:
        names = ", ".join(_DOMAIN_LABELS.get(d, d) for d in thin)
        st.info(
            f"💡 **{names}** has no jobs in the tracker yet — run a Discovery "
            "search for it on the Jobs page, or paste links on the "
            "**Jobs → Share a Job** tab to seed it."
        )


def show_overview() -> None:
    """Show overview page."""
    st.header("📈 Overview")

    # 🔕 Vacation-mode banner: when alerts are paused, surface it right at
    # the top so it's never forgotten.
    try:
        _prefs_banner = (
            fetch_data(f"/notifications/preferences/{_current_user_id()}") or {}
        )
        _pu = _prefs_banner.get("paused_until")
        if _pu:
            _parsed_pu = datetime.fromisoformat(str(_pu).replace("Z", "+00:00"))
            if _parsed_pu.tzinfo is None:
                _parsed_pu = _parsed_pu.replace(tzinfo=UTC)
            if _parsed_pu > datetime.now(UTC):
                st.warning(
                    f"🔕 **Alerts are paused** until {_pu} — no emails or "
                    "Telegram pings are being sent. Resume them anytime on "
                    "the Settings page."
                )
    except Exception:  # noqa: BLE001, S110 - banner must never break the page
        pass

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

        # ── 🗂 Domain coverage (live per-category counts) ───────────────
        _domain_coverage_section()

        # ── 🎯 Job of the day (best resume match) ─────────────────────────
        # The same highlight the daily email / Telegram digest leads with:
        # the highest match % against the user's uploaded resume. Only shows
        # when a resume exists (no match scores yet otherwise).
        jotd = _my_top_matches(_current_user_id(), limit=1)
        if jotd:
            jotd_job, jotd_score, jotd_match = jotd[0]
            jtitle = str(jotd_job.get("title") or "Untitled role")
            jcompany = str(jotd_job.get("company") or "Unknown")
            st.markdown(
                "<div style='background:linear-gradient(135deg,#f59e0b 0%,"
                "#ef4444 100%);border-radius:16px;padding:18px 24px;"
                "color:white;margin:6px 0 4px 0;box-shadow:0 6px 20px "
                "rgba(239,68,68,0.25);'>"
                "<div style='font-size:12px;font-weight:800;"
                "letter-spacing:1px;text-transform:uppercase;opacity:0.9;'>"
                "🎯 Job of the day</div>"
                f"<div style='font-size:19px;font-weight:800;margin:4px 0;'>"
                f"{escape(jtitle)}</div>"
                f"<div style='font-size:13px;opacity:0.95;'>"
                f"{escape(jcompany)} · "
                f"{escape(str(jotd_job.get('location') or 'Remote'))}",
                unsafe_allow_html=True,
            )
            # Closing tag rendered separately (Streamlit needs the opening
            # div rendered with unsafe_allow_html too, or the raw HTML
            # leaks as plain text instead of a styled card).
            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )
            act_cols = st.columns([3, 2])
            with act_cols[0]:
                st.markdown(
                    f"<span class='chip' style='color:#fff;background:rgba(255,255,255,0.2);"
                    f"border-color:rgba(255,255,255,0.35);font-weight:700;'>"
                    f"Match {jotd_score:.0f}%</span> "
                    f"<span class='chip' style='color:#fff;background:rgba(255,255,255,0.2);"
                    f"border-color:rgba(255,255,255,0.35);'>"
                    f"Same as your daily digest highlight</span>",
                    unsafe_allow_html=True,
                )
            with act_cols[1]:
                if jotd_job.get("url"):
                    st.link_button(
                        "🔗 View & Apply",
                        jotd_job["url"],
                        key=f"jotd_{jotd_job.get('id')}",
                        use_container_width=True,
                    )

        # ── Trending this week (engagement-ranked) ────────────────────────
        trending = fetch_data("/jobs/trending?days=14&limit=6") or {}
        trend_jobs = trending.get("trending") or []
        if trend_jobs:
            st.markdown(
                '<div class="section-title">🔥 Trending this week</div>'
                '<div class="section-sub">Most applied / saved / viewed jobs '
                "from the last 14 days — use 👁 Mark viewed on any job card to "
                "boost its rank.</div>",
                unsafe_allow_html=True,
            )
            for rank, tj in enumerate(trend_jobs, start=1):
                with st.container(border=True):
                    tcol_l, tcol_r = st.columns([4, 1])
                    with tcol_l:
                        st.markdown(
                            f"**#{rank}** · "
                            f"{escape(str(tj.get('title') or 'Untitled'))}"
                        )
                        tchips = []
                        if tj.get("company"):
                            tchips.append(f"🏢 {escape(str(tj['company']))}")
                        if tj.get("location"):
                            tchips.append(f"📍 {escape(str(tj['location']))}")
                        if tchips:
                            st.markdown(
                                '<div class="chip-row">'
                                + "".join(
                                    f'<span class="chip">{c}</span>' for c in tchips
                                )
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                        st.caption(
                            f"👁 {int(tj.get('views', 0))} views · "
                            f"📋 {int(tj.get('applications', 0))} applied · "
                            f"📌 {int(tj.get('bookmarks', 0))} saved"
                        )
                    with tcol_r:
                        tj_id = str(tj.get("id") or "")
                        if st.button(
                            "👁 Mark viewed",
                            key=f"trend_view_{tj_id}",
                            use_container_width=True,
                            help="Counts this job as viewed (raises its 🔥 rank).",
                        ):
                            _api(f"/jobs/{tj_id}/view", method="POST", timeout=15)
                        if tj.get("url"):
                            st.link_button(
                                "🔗 Open",
                                tj["url"],
                                key=f"trend_open_{tj_id}",
                                use_container_width=True,
                            )
            st.markdown("")

        # ── ⏳ Closing soon (expiring roles) ─────────────────────────────
        closing = fetch_data("/jobs/closing/soon") or []
        if isinstance(closing, list) and closing:
            st.markdown(
                '<div class="section-title">⏳ Closing soon</div>'
                '<div class="section-sub">Deadlines are approaching — '
                "apply before these roles close.</div>",
                unsafe_allow_html=True,
            )
            for cj in closing[:5]:
                with st.container(border=True):
                    ccol_l, ccol_r = st.columns([4, 1])
                    with ccol_l:
                        st.markdown(f"**{escape(str(cj.get('title') or 'Untitled'))}**")
                        cchips = []
                        if cj.get("company"):
                            cchips.append(f"🏢 {escape(str(cj['company']))}")
                        if cj.get("location"):
                            cchips.append(f"📍 {escape(str(cj['location']))}")
                        if cj.get("expires_at"):
                            try:
                                exp = datetime.fromisoformat(str(cj["expires_at"]))
                                cchips.append(f"⏳ {exp:%b %d}")
                            except ValueError:
                                pass
                        if cchips:
                            st.markdown(
                                '<div class="chip-row">'
                                + "".join(
                                    f'<span class="chip">{c}</span>' for c in cchips
                                )
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                    with ccol_r:
                        if cj.get("url"):
                            st.link_button(
                                "🔗 Open",
                                cj["url"],
                                key=f"close_open_{cj.get('id')}",
                                use_container_width=True,
                            )

        # ── 🗓 Upcoming interviews (countdown) ────────────────────────────
        # Applications with an interview_at in the future, sorted by date,
        # with a days-to-go countdown chip. Falls back silently when the
        # user has no interviews scheduled or the API is unreachable.
        try:
            _uid = _current_user_id()
            _apps_data = fetch_data(f"/applications/?user_id={_uid}&limit=100") or {}
            # The applications API doesn't embed job details; look titles up
            # from the jobs list so the card says "Security Analyst @ X".
            _jobs_lookup: dict[str, dict] = {}
            with suppress(Exception):
                _jobs_data = fetch_data("/jobs/?limit=100") or {}
                _jobs_lookup = {
                    str(j.get("id")): j for j in (_jobs_data.get("jobs") or [])
                }
            _interviews = []
            _now = datetime.now(UTC)
            for _a in _apps_data.get("applications") or []:
                _ia = _a.get("interview_at")
                if not _ia:
                    continue
                try:
                    _dt = datetime.fromisoformat(str(_ia).replace("Z", "+00:00"))
                    if _dt.tzinfo is None:
                        _dt = _dt.replace(tzinfo=UTC)
                    if _dt >= _now:
                        _interviews.append((_dt, _a))
                except ValueError:
                    continue
            _interviews.sort(key=lambda pair: pair[0])
            if _interviews:
                st.markdown(
                    '<div class="section-title">🗓 Upcoming interviews</div>'
                    '<div class="section-sub">Your scheduled interviews — '
                    "don't miss them!</div>",
                    unsafe_allow_html=True,
                )
                for _dt, _a in _interviews[:6]:
                    _days = (_dt - _now).days
                    _countdown = "Today" if _days <= 0 else f"in {_days}d"
                    _job = _jobs_lookup.get(str(_a.get("job_id") or ""), {}) or {}
                    _label = str(_job.get("title") or "Interview") + (
                        f" @ {_job.get('company')}" if _job.get("company") else ""
                    )
                    with st.container(border=True):
                        _icol_l, _icol_r = st.columns([4, 1])
                        with _icol_l:
                            st.markdown(
                                f"**🗓 {_dt:%a, %b %d at %H:%M}** · {escape(_label)}"
                            )
                        with _icol_r:
                            st.markdown(
                                f'<div class="chip" style="color:#7c3aed;'
                                f"border-color:rgba(124,58,237,0.35);"
                                f'font-weight:700;">⏱ {_countdown}</div>',
                                unsafe_allow_html=True,
                            )
        except Exception:  # noqa: BLE001, S110 - interviews must never break the page
            pass

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

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔍 Discovery", "📋 Saved Jobs", "🔗 Share a Job", "🗄 Expired"]
    )

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

    # ------ Tab 3: Share / Import jobs (paste any link) ------
    with tab3:
        _share_job_form()
        st.divider()
        _bulk_import_form()

    # ------ Tab 4: Expired / archived jobs ------
    with tab4:
        _expired_jobs_tab()


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

    # Resume match on every card — one click, cached in the session. The
    # full match payload is kept (not just the score) so each card renders
    # the matched/related/missing-skill breakdown and the min-score slider
    # below can hide weaker matches.
    match_data: dict = st.session_state.get("saved_job_match_data") or {}
    if st.button("🎯 Match these jobs to my resume", use_container_width=True):
        with st.spinner("Matching against your resume..."):
            job_ids = [j["id"] for j in jobs if j.get("id")][:50]
            if job_ids:
                result = _match_jobs_to_resume(jobs, _current_user_id())
                if result and result.get("matches"):
                    match_data = {str(m.get("job_id")): m for m in result["matches"]}
                    st.session_state["saved_job_match_data"] = match_data
                    st.success(
                        f"✅ Matched {len(match_data)} jobs — average "
                        f"{result.get('average_score')}%"
                    )
                else:
                    st.info(
                        "No match scores — upload your resume on the Resume "
                        "Match page first."
                    )
    elif not match_data:
        st.caption(
            "💡 Click **Match these jobs to my resume** to see your match % "
            "and skill breakdown on every card."
        )

    # Minimum-match filter: hides cards below the slider value, but only
    # for jobs that were part of a match run (unmatched jobs stay visible).
    min_match = 0
    if match_data:
        min_match = st.slider(
            "🎯 Only show matches at least this strong",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
            help="Filters the sections below to jobs whose resume match % is "
            "at or above this value. Jobs you haven't matched are unaffected.",
        )

    # 📥 Export the currently filtered view (location filter applied) as
    # CSV, including each job's resume match % when a match run happened.
    import csv
    import io

    csv_cols = [
        "title",
        "company",
        "location",
        "url",
        "source",
        "salary_min",
        "salary_max",
        "salary_currency",
        "is_remote",
        "posted_at",
        "match_score",
    ]
    csv_buf = io.StringIO()
    csv_writer = csv.DictWriter(csv_buf, fieldnames=csv_cols, extrasaction="ignore")
    csv_writer.writeheader()
    for job in jobs:
        row = dict(job)
        m = match_data.get(str(job.get("id")))
        row["match_score"] = m.get("match_score") if m else ""
        csv_writer.writerow(row)
    st.download_button(
        "📥 Export CSV",
        data=csv_buf.getvalue(),
        file_name="saved_jobs.csv",
        mime="text/csv",
        help="Downloads the currently filtered jobs (location filter applied) "
        "as a spreadsheet-friendly CSV.",
    )

    # Render sections. Filter each category by the min-match slider FIRST
    # so a section whose every card fell below the slider disappears
    # entirely (no stale header with zero cards), and the header count
    # reflects what's actually shown.
    domains = domains_present if selected == "All" else [selected]
    for domain in domains:
        items = grouped.get(domain)
        if not items:
            continue
        visible = []
        for job in items:
            match = match_data.get(str(job.get("id")))
            if match is not None:
                score = match.get("match_score")
                if isinstance(score, (int, float)) and min_match and score < min_match:
                    continue
            visible.append(job)
        if not visible:
            continue
        _category_header(domain, len(visible), len(jobs))
        for job in visible:
            _render_job(job, match_data.get(str(job.get("id"))))


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


def _bulk_import_form() -> None:
    """Bulk import: paste up to 8 job links at once; each saved like /share."""
    st.markdown(
        '<div class="section-title">📥 Import Multiple Links</div>'
        '<div class="section-sub">Found a list of roles on LinkedIn, Naukri, '
        "Internshala, a company page…? Paste up to 8 links (one per line) and "
        "they're all saved in one go — perfect for sharing a batch with your "
        "team or seeding a friend's digest.</div>",
        unsafe_allow_html=True,
    )
    with st.form("bulk_import_form", clear_on_submit=True):
        links_text = st.text_area(
            "Job links (one per line, up to 8)",
            placeholder=(
                "https://www.linkedin.com/jobs/view/...\n"
                "https://www.naukri.com/job-listings-...\n"
                "https://internshala.com/job/detail/..."
            ),
            height=130,
        )
        submitted = st.form_submit_button("🚀 Import all", use_container_width=True)

    if submitted:
        urls = [
            line.strip()
            for line in (links_text or "").splitlines()
            if line.strip().startswith(("http://", "https://"))
        ]
        if not urls:
            st.error("Paste at least one job link (https://...) — one per line.")
            return
        urls = urls[:8]
        with st.spinner(
            f"Importing {len(urls)} link(s)... this can take up to a minute."
        ):
            resp = _api_raw(
                "/jobs/import-links",
                method="POST",
                json_data={"urls": urls},
                timeout=75,
            )
        if resp is None:
            st.error("Import API unreachable. Is the API server running?")
            return
        if resp.status_code not in (200, 201):
            st.error(
                "Import failed — please try again or paste the links one at a time."
            )
            return
        data = resp.json()
        parts = [f"✅ **{data.get('saved', 0)} saved**"]
        parts.append(f"ℹ️ {data.get('duplicates', 0)} duplicate(s)")
        if data.get("skipped"):
            parts.append(f"⏭️ {data.get('skipped', 0)} skipped (time limit)")
        parts.append(f"❌ {data.get('failed', 0)} failed")
        st.success(" · ".join(parts))
        for r in data.get("results") or []:
            job = r.get("job") or {}
            url = str(r.get("url") or "")[:70]
            if r.get("error"):
                st.caption(f"❌ {escape(url)} — {escape(r['error'])}")
            elif r.get("duplicate"):
                st.caption(f"ℹ️ {escape(url)} — already saved")
            else:
                st.caption(
                    f"✅ {escape(str(job.get('title') or 'Job'))} · "
                    f"{escape(str(job.get('company') or 'Unknown'))}"
                )
        if data.get("failed"):
            st.caption(
                "💡 Links that failed can be saved one-by-one in the form above — "
                "just paste the title manually if auto-detection can't read the page."
            )


def _expired_jobs_tab() -> None:
    """Expired jobs: archived listings moved out of the live feed.

    Stale jobs (older than 30 days, never re-verified) are archived into a
    separate ``expired_jobs`` table so the live Saved Jobs feed stays fresh.
    This tab shows the archive with a one-click "archive stale jobs" action
    that runs the same cleanup the scheduler uses.
    """
    st.markdown(
        '<div class="section-title">🗄 Expired / Archived Jobs</div>'
        '<div class="section-sub">Roles older than 30 days are moved here so '
        "your live feed only shows fresh, active jobs. Nothing is deleted — "
        "the archive is just kept out of the daily alerts.</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(
            "Run the same cleanup the scheduler performs to move stale jobs "
            "(30+ days old) into this archive."
        )
    with col2:
        if st.button(
            "🧹 Archive stale jobs", use_container_width=True, key="archive_stale_btn"
        ):
            with st.spinner("Archiving stale jobs..."):
                result = _api_raw(
                    "/jobs/archive-expired?days=30", method="POST", timeout=30
                )
            if result is not None and result.status_code == 200:
                archived = (result.json() or {}).get("archived", 0)
                if archived:
                    st.success(
                        f"✅ Archived **{archived}** stale job(s) — the feed is fresh again."
                    )
                else:
                    st.info("No stale jobs to archive — everything is already fresh.")
                st.rerun()
            else:
                st.error("Archive API unreachable. Is the API server running?")

    data = fetch_data("/jobs/expired?limit=50")
    expired = (data or {}).get("expired_jobs") or []
    total = (data or {}).get("total") or 0

    if not expired:
        st.info("The archive is empty — nothing has expired yet. 🎉")
        return

    _stat_tile(total, "Archived jobs")
    st.markdown("")
    for item in expired:
        title = escape(str(item.get("title") or "Untitled"))
        company = escape(str(item.get("company") or ""))
        location = escape(str(item.get("location") or ""))
        reason = escape(str(item.get("reason") or ""))
        expired_when = _time_ago(item.get("expired_at"))
        with st.container(border=True):
            st.markdown(f"<div class='job-title'>{title}</div>", unsafe_allow_html=True)
            chips = []
            if company and company != "Unknown":
                chips.append(f"🏢 {company}")
            if location:
                chips.append(f"📍 {location}")
            if reason:
                chips.append(f"🚫 {reason}")
            if chips:
                st.markdown(
                    '<div class="chip-row">'
                    + "".join(f'<span class="chip">{c}</span>' for c in chips)
                    + "</div>",
                    unsafe_allow_html=True,
                )
            st.caption(f"🗄 Expired {expired_when}")


# ---------------------------------------------------------------------------
# Page: Applications
# ---------------------------------------------------------------------------


def _follow_ups_panel() -> None:
    """'⏰ Follow-ups needed' panel for the Applications page.

    Surfaces the same pending applications the daily digest reminds the
    user about (applied/interview, not yet marked followed up), sorted
    most-urgent-first, with a one-click 'Mark followed up' action that
    stops the digest from nudging them again.
    """
    user_id = _current_user_id()
    data = fetch_data(f"/applications/follow-ups?user_id={user_id}") or {}
    follow_ups = data.get("follow_ups") or []

    if not follow_ups:
        return

    st.subheader("⏰ Follow-ups needed")
    st.caption(
        "Applications that have been sitting for a while — a quick follow-up "
        "email often revives them. (These also appear in your daily digest.)"
    )
    for item in follow_ups:
        title = escape(str(item.get("job_title") or "Unknown role"))
        company = escape(str(item.get("company") or ""))
        days = int(item.get("days_since") or 0)
        app_id = str(item.get("application_id") or "")
        when = "today" if days == 0 else f"{days}d ago"
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.markdown(f"**{title}**" + (f" · {company}" if company else ""))
            job_url = item.get("job_url")
            if job_url:
                st.link_button(
                    "🔗 View job",
                    job_url,
                    key=f"follow_link_{app_id}",
                )
        with col2:
            st.markdown(
                f'<span class="chip">⏳ {when}</span>',
                unsafe_allow_html=True,
            )
        with col3:
            if st.button(
                "✅ Mark followed up",
                key=f"follow_up_{app_id}",
                use_container_width=True,
            ):
                resp = _api_raw(
                    f"/applications/{app_id}/reminded",
                    method="POST",
                    timeout=15,
                )
                if resp is not None and resp.status_code == 200:
                    st.rerun()
                else:
                    st.error(
                        "Couldn't mark as followed up — is the API server running?"
                    )
        st.divider()


def _priority_panel() -> None:
    """'⭐ Priority applications' panel for the Applications page.

    Lists the applications the user pinned as high-priority (via the ⭐
    toggle on each application), most important first, with a View link.
    Hidden entirely when nothing is pinned.
    """
    user_id = _current_user_id()
    data = fetch_data(f"/applications/priority?user_id={user_id}") or {}
    priority_apps = data.get("applications") or []
    if not priority_apps:
        return

    job_rows = fetch_data("/jobs/?limit=200") or {}
    job_lookup = {str(j.get("id")): j for j in (job_rows.get("jobs") or [])}

    st.subheader("⭐ Priority applications")
    st.caption(
        "The applications you care about most — use the ⭐ High-priority "
        "toggle on any application to pin it here."
    )
    for app in priority_apps:
        job = job_lookup.get(str(app.get("job_id"))) or {}
        title = escape(str(job.get("title") or "Unknown role"))
        company = escape(str(job.get("company") or ""))
        app_id = str(app.get("id") or "")
        raw_status = str(app.get("status") or "")
        status_label = _STATUS_LABELS.get(raw_status, raw_status.capitalize())
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"⭐ **{title}**" + (f" · {company}" if company else ""))
            st.caption(status_label)
        with col2:
            url = job.get("url")
            if url:
                st.link_button("🔗 View", url, key=f"prio_link_{app_id}")
        st.divider()


def show_applications() -> None:
    """Show and manage applications."""
    st.header("📋 Applications")

    # ── Follow-ups needed ─────────────────────────────────────────────
    _follow_ups_panel()

    # ── ⭐ Priority applications ──────────────────────────────────────
    _priority_panel()

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

    apps = (apps_data or {}).get(
        "applications"
    ) or []  # 📥 Export the current (filtered) application list to CSV.
    if apps:
        import csv
        import io

        # The applications API doesn't embed job details, so enrich titles /
        # companies from a fresh jobs lookup (best-effort; blank when the
        # job list is unreachable).
        job_rows = fetch_data("/jobs/?limit=200") or {}
        job_lookup = {str(j.get("id")): j for j in (job_rows.get("jobs") or [])}
        csv_cols = [
            "id",
            "job_id",
            "status",
            "created_at",
            "updated_at",
            "job_title",
            "company",
        ]
        csv_buf = io.StringIO()
        csv_writer = csv.DictWriter(csv_buf, fieldnames=csv_cols, extrasaction="ignore")
        csv_writer.writeheader()
        for app in apps:
            job = job_lookup.get(str(app.get("job_id"))) or {}
            csv_writer.writerow(
                {
                    **app,
                    "job_title": job.get("title") if isinstance(job, dict) else "",
                    "company": job.get("company") if isinstance(job, dict) else "",
                }
            )
        st.download_button(
            "📥 Export Applications CSV",
            data=csv_buf.getvalue(),
            file_name="applications.csv",
            mime="text/csv",
            help="Downloads the current status filter (or all applications) "
            "as a spreadsheet-friendly CSV, with job titles from the live "
            "job list.",
        )

    if apps:
        for app in apps:
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

                # ── ⭐ High-priority toggle ─────────────────────────────
                _is_high = int(app.get("priority") or 0) >= 1
                _toggled = st.checkbox(
                    "⭐ High priority",
                    value=_is_high,
                    key=f"prio_{app['id']}",
                )
                if _toggled != _is_high:
                    _set_application_priority(app["id"], 1 if _toggled else 0)

                # ── Notes editor ───────────────────────────────────────
                notes = st.text_area(
                    "📝 Notes",
                    value=app.get("notes") or "",
                    placeholder=(
                        "e.g. HR call on Friday, asked about SOC shift timings…"
                    ),
                    key=f"notes_{app['id']}",
                )
                if st.button(
                    "💾 Save notes",
                    key=f"save_notes_{app['id']}",
                    use_container_width=True,
                ):
                    _save_application_notes(app["id"], notes)

                # ── Status-change timeline ─────────────────────────────
                if st.button(
                    "🕘 Show status history",
                    key=f"hist_{app['id']}",
                    use_container_width=True,
                ):
                    hist = fetch_data(f"/applications/{app['id']}/history")
                    entries = (hist or {}).get("history") or []
                    if not entries:
                        st.caption(
                            "No status changes yet — every update you make "
                            "from now on appears here."
                        )
                    else:
                        for entry in entries:
                            raw_status = str(entry.get("status", "?"))
                            label = _STATUS_LABELS.get(
                                raw_status, raw_status.capitalize()
                            )
                            when = str(entry.get("changed_at") or "")[:10]
                            note = (entry.get("notes") or "").strip()
                            st.markdown(
                                f"• **{escape(label)}**"
                                + (f" — {when}" if when else "")
                                + (f"\n\n  📝 {escape(note)}" if note else "")
                            )
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

    # ── 📊 Application funnel (saved → applied → interview → offer) ───────
    # Built from the same status_counts the overview metric cards use, so
    # the funnel always matches the headline numbers. Conversion % between
    # consecutive stages shows exactly where applications stall.
    try:
        _funnel_uid = _current_user_id()
        _overview = fetch_data(f"/dashboard/overview?user_id={_funnel_uid}") or {}
        _sc = (_overview.get("applications") or {}).get("status_counts") or {}
        if _sc:
            _stage_order = ["saved", "applied", "interview", "offer"]
            _stage_labels = {
                "saved": "📌 Saved",
                "applied": "📨 Applied",
                "interview": "🗓 Interview",
                "offer": "🎉 Offer",
            }
            _funnel = [
                {"stage": _stage_labels.get(s, s), "count": int(_sc.get(s, 0) or 0)}
                for s in _stage_order
            ]
            _funnel = [f for f in _funnel if f["count"] > 0]
            if len(_funnel) >= 2:
                st.subheader("📊 Application Funnel")
                _fig = px.funnel(
                    _funnel,
                    x="count",
                    y="stage",
                    title=None,
                )
                _fig.update_traces(
                    textinfo="value+percent initial",
                    marker={
                        "color": ["#64748b", "#3b82f6", "#8b5cf6", "#10b981"][
                            : len(_funnel)
                        ]
                    },
                )
                st.plotly_chart(_fig, use_container_width=True)
                # Conversion % between consecutive stages
                _conv = []
                for _i in range(1, len(_funnel)):
                    _prev = _funnel[_i - 1]["count"]
                    if _prev:
                        _pct = _funnel[_i]["count"] / _prev * 100
                        _conv.append(
                            f"{_funnel[_i - 1]['stage']} → {_funnel[_i]['stage']}: "
                            f"{_pct:.0f}%"
                        )
                if _conv:
                    st.caption(" ↔ ".join(_conv))
    except Exception:  # noqa: BLE001, S110 - funnel must never break the page
        pass


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

    # Role × city benchmark table from real stored postings.
    bench = _api("/salary/benchmarks")
    rows = (bench or {}).get("rows") or []
    if rows:
        st.subheader("📊 Role × City benchmarks")
        st.markdown(
            "Median / avg / min / max from the jobs actually tracked — "
            'answers "what does a SOC Analyst in Bangalore pay?"'
        )
        table = []
        for r in rows[:60]:
            currency = r.get("currency", "INR")
            if currency == "INR":
                table.append(
                    {
                        "Role": r["domain"].title(),
                        "City": r["city"],
                        "Jobs": r["count"],
                        "Median": f"₹{r['median']:,.0f}",
                        "Avg": f"₹{r['average']:,.0f}",
                        "Range": f"₹{r['min']:,.0f} – ₹{r['max']:,.0f}",
                    }
                )
            else:
                table.append(
                    {
                        "Role": r["domain"].title(),
                        "City": r["city"],
                        "Jobs": r["count"],
                        "Median": f"${r['median']:,.0f}",
                        "Avg": f"${r['average']:,.0f}",
                        "Range": f"${r['min']:,.0f} – ${r['max']:,.0f}",
                    }
                )
        st.dataframe(table, use_container_width=True, hide_index=True)
        top_cities = (bench or {}).get("top_cities") or []
        if top_cities:
            st.caption(
                "Most benchmarked cities: "
                + ", ".join(f"{c['city']} ({c['buckets']})" for c in top_cities)
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
    "sms": "📱 SMS",
    "whatsapp": "🟢 WhatsApp",
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
    _user_profile_settings = _current_user() or {}
    saved_telegram_chat_id = _user_profile_settings.get("telegram_chat_id") or None

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

    # Telegram chat-ID helper (only meaningful when Telegram is configured).
    if "telegram" in configured:
        st.markdown("---")
        _telegram_finder_block(saved_telegram_chat_id, auto_save=True)

    # SMS phone-number helper (only meaningful when SMS/Twilio is configured
    # and a registered account is signed in — legacy user1 has no profile).
    if "sms" in configured and _current_user():
        st.markdown("---")
        st.markdown(
            "**📱 SMS alerts** — add your phone number (with country code) "
            "and tick **SMS** in the delivery channels above to get your "
            "digest by text too."
        )
        saved_phone = (_user_profile_settings.get("phone_number") or "").strip()
        phone = st.text_input(
            "Your phone number (E.164)",
            value=saved_phone,
            placeholder="+919876543210",
            help="Include the country code — e.g. +91 for India.",
        )
        if phone.strip() and phone.strip() != saved_phone:
            phone_resp = _api(
                f"/users/{_current_user_id()}",
                method="PUT",
                json_data={"phone_number": phone.strip()},
                timeout=15,
            )
            if phone_resp:
                st.session_state["user"] = {
                    **_current_user(),
                    "phone_number": phone.strip(),
                }
                st.success(
                    "✅ Phone number saved — SMS alerts will use it. "
                    "Tick **SMS** in Delivery channels and Save."
                )
            else:
                st.error("Couldn't save the phone number — API unreachable.")

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
    chan_options = [c for c in ("email", "telegram", "sms") if c in configured]
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
    instant_alerts = st.checkbox(
        "⚡ Instant Telegram alert for new high-match jobs",
        value=bool(prefs.get("instant_alerts", True)),
        help="When a newly discovered job matches your categories, location "
        "and match threshold, ping you on Telegram right away instead of "
        "waiting for the next daily slot. Needs your Telegram chat ID. "
        "With this on, the scheduled digest skips Telegram for you (so you "
        "never get the same job twice) — your email digest still arrives "
        "in full.",
    )
    if not saved_telegram_chat_id:
        st.caption(
            "🔒 Save your Telegram chat ID first (use the 📱 finder above), "
            "then the test button unlocks."
        )
    if st.button(
        "🚀 Send Test Instant Alert",
        use_container_width=True,
        disabled=not saved_telegram_chat_id,
        help="Sends a sample instant-alert message to your Telegram right now "
        "so you can see exactly what a new high-match job will look like.",
    ):
        with st.spinner("Sending test ping to your Telegram..."):
            result = _api(
                "/notifications/instant-alert/test",
                method="POST",
                json_data={"user_id": user_id},
                timeout=30,
            )
        if result:
            if result.get("sent"):
                st.success(
                    "✅ Test instant alert sent to your Telegram! It should "
                    "have arrived just now — that's exactly what a new "
                    "high-match job ping looks like."
                )
            else:
                hint = result.get("hint") or "Delivery failed."
                st.error(f"⚠️ {hint}")
        else:
            st.error("Send failed — is the API reachable?")

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
                "instant_alerts": instant_alerts,
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

    # --------------------------------------------------------------
    # 👀 Preview — see exactly what the next digest would contain
    # --------------------------------------------------------------
    st.markdown("---")
    st.markdown(
        "**👀 Preview my next digest** — see exactly which jobs the next "
        "scheduled send would include (your categories, your location, your "
        "match %). Nothing is sent; this is a pure lookahead."
    )
    if st.button("🔎 Show digest preview", use_container_width=True):
        with st.spinner("Building your digest preview..."):
            preview = _api(
                f"/notifications/preferences/{user_id}/preview",
                method="GET",
                timeout=60,
            )
        if preview:
            preview_jobs = preview.get("jobs") or []
            p_loc = preview.get("location") or "any location"
            p_doms = ", ".join(preview.get("domains") or []) or "all categories"
            st.caption(
                f"Scope: **{escape(str(p_doms))}** · 📍 **{escape(str(p_loc))}** "
                f"· remote/WFH {'included' if preview.get('include_remote') else 'excluded'}"
            )
            if not preview_jobs:
                st.info(
                    "Your next digest would be empty with the current "
                    "settings — either no new jobs since your last alert, or "
                    "none pass your category/location/match filters. Try a "
                    "broader category or run a Discovery search."
                )
            else:
                st.success(
                    f"📦 {len(preview_jobs)} job(s) would be sent at the next "
                    "scheduled slot."
                )
                for pj_i, pj in enumerate(preview_jobs):
                    pj_title = escape(str(pj.get("title") or "Untitled role"))
                    pj_company = escape(str(pj.get("company") or "Unknown"))
                    pj_loc = escape(str(pj.get("location") or "Remote"))
                    pj_score = pj.get("match_score")
                    pj_score_txt = (
                        f" · 🎯 {pj_score:.0f}%"
                        if isinstance(pj_score, (int, float))
                        else ""
                    )
                    st.markdown(f"**{pj_title}**{pj_score_txt}")
                    st.caption(f"🏢 {pj_company} · 📍 {pj_loc}")
                    if pj.get("url"):
                        st.link_button(
                            "🔗 View",
                            pj["url"],
                            key=f"prev_{pj_i}_{pj.get('title')}",
                        )
                    st.divider()
        else:
            st.error("Preview failed — is the API reachable?")

    # --------------------------------------------------------------
    # 🔕 Vacation mode — pause ALL alerts until a chosen date
    # --------------------------------------------------------------
    st.markdown("---")
    st.markdown(
        "**🔕 Vacation mode** — pause *all* alerts (daily email, Telegram,"
        " weekly recap, instant pings) until a date you pick. Handy for "
        "holidays or exam weeks; discovery keeps running, delivery just "
        "stops."
    )
    paused_until = prefs.get("paused_until")
    is_paused = False
    if paused_until:
        with suppress(Exception):
            parsed = datetime.fromisoformat(str(paused_until).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            is_paused = bool(parsed > datetime.now(UTC))
    if is_paused:
        st.info(
            f"⏸ Alerts are paused until **{paused_until}** — no emails or "
            "Telegram pings are being sent."
        )
        if st.button("▶️ Resume alerts now", use_container_width=True):
            result = _api(
                f"/notifications/preferences/{user_id}",
                method="PUT",
                json_data={"resume_alerts": True},
                timeout=15,
            )
            st.success("✅ Alerts resumed — you'll get the next scheduled digest.")
    else:
        pause_days = st.selectbox(
            "Pause alerts for",
            [1, 2, 3, 7, 14],
            format_func=lambda d: f"{d} day{'s' if d > 1 else ''}",
        )
        if st.button("🔕 Pause my alerts", use_container_width=True):
            with suppress(Exception):
                until = datetime.now(UTC) + timedelta(days=pause_days)
                result = _api(
                    f"/notifications/preferences/{user_id}",
                    method="PUT",
                    json_data={"paused_until": until.isoformat()},
                    timeout=15,
                )
                if result:
                    st.success(
                        f"✅ Alerts paused until **{until.strftime('%d %b %Y')}** "
                        "(UTC). Enjoy the break!"
                    )
                else:
                    st.error("Couldn't pause — is the API reachable?")

    # --------------------------------------------------------------
    # 🛠 Maintenance — one-click backfills / archive
    # --------------------------------------------------------------
    st.markdown("---")
    st.markdown(
        "**🛠 Maintenance** — one-click housekeeping on the live database. "
        "Safe to run anytime; each reports how many rows it changed."
    )
    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        if st.button(
            "🏷 Backfill tags",
            use_container_width=True,
            help="Derive skill tags for jobs saved before auto-tagging, so "
            "they earn real match % and ATS scores.",
        ):
            result = _api("/jobs/backfill-tags", method="POST", timeout=120)
            st.success(
                f"✅ Tagged {result.get('updated', 0)} jobs."
                if result
                else "⚠️ Backfill failed — API unreachable."
            )
    with mcol2:
        if st.button(
            "👁 Backfill views",
            use_container_width=True,
            help="Seed view counts from real applications + bookmarks so 🔥 "
            "Trending ranks jobs with actual activity.",
        ):
            result = _api("/jobs/backfill-engagement", method="POST", timeout=120)
            st.success(
                f"✅ Updated {result.get('updated', 0)} jobs."
                if result
                else "⚠️ Backfill failed — API unreachable."
            )
    with mcol3:
        if st.button(
            "🗑 Archive expired",
            use_container_width=True,
            help="Deactivate jobs with deadlines older than 14 days so live "
            "listings stay fresh.",
        ):
            result = _api("/jobs/archive-expired?days=14", method="POST", timeout=120)
            st.success(
                f"✅ Archived {result.get('archived', 0)} jobs."
                if result
                else "⚠️ Archive failed — API unreachable."
            )

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

    # --------------------------------------------------------------
    # 👁 Preview today's digest — see it before it's sent (no sending,
    # no duplicate-window advance; uses GET /reports/daily?preview=1)
    # --------------------------------------------------------------
    with st.expander("👁 Preview today's digest"):
        st.markdown(
            "See exactly what today's alert contains right now — the same "
            "job list the email / Telegram would deliver. Previewing never "
            "sends anything and never skips jobs from the real digest."
        )
        if st.button("📄 Build today's digest preview", use_container_width=True):
            with st.spinner("Fetching today's filtered jobs..."):
                preview = fetch_data("/reports/daily?preview=1")
            if not preview:
                st.error("Couldn't build the preview — is the API reachable?")
            else:
                jobs = preview.get("new_jobs") or []
                total = preview.get("summary", {}).get("new_jobs", 0)
                if not jobs:
                    st.info(
                        "No new jobs match your categories yet — the digest "
                        "will be empty until discovery finds something fresh. "
                        "Check the Jobs page to run a discovery."
                    )
                else:
                    st.success(
                        f"**{total} jobs** would be in today's digest "
                        "(categorised below)."
                    )
                    _domains_groups: dict[str, list] = {}
                    for jb in jobs:
                        dkey = str(jb.get("domain") or "other")
                        _domains_groups.setdefault(dkey, []).append(jb)
                    for dkey, items in _domains_groups.items():
                        dlabel = _DOMAIN_LABELS.get(dkey, dkey)
                        dicon = _CATEGORY_STYLE.get(dkey, {}).get("icon", "📂")
                        with st.expander(f"{dicon} {dlabel} ({len(items)})"):
                            for jb in items[:8]:
                                ptitle = escape(str(jb.get("title") or "Untitled"))
                                pcomp = escape(str(jb.get("company") or ""))
                                ploc = escape(str(jb.get("location") or "Remote"))
                                st.markdown(f"**{ptitle}** · {pcomp} · 📍 {ploc}")
                                if jb.get("url"):
                                    st.link_button(
                                        "🔗 View",
                                        jb["url"],
                                        key=f"prev_{jb.get('id')}_{dkey}",
                                    )

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
