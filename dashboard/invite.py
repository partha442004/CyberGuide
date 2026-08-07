"""Invite-a-friend helpers for the InternTrack dashboard.

Pure functions (no Streamlit imports) so they can be unit-tested without a
Streamlit runtime. The app layer reads ``st.query_params`` and passes the raw
values here for parsing / validation; ``build_invite_link`` produces the
share URL a signed-in user sends to a friend so their signup form is
pre-filled with the referrer's location and categories.
"""

from __future__ import annotations

from urllib.parse import quote

# Domain keys understood by the API (mirrors the dashboard's _DOMAIN_ORDER).
KNOWN_DOMAINS = frozenset(
    {"security", "coding", "data", "design", "finance", "marketing", "other"}
)

DEFAULT_DASHBOARD_URL = "https://cyberguide2026aug.streamlit.app/"


def build_invite_link(
    *,
    base_url: str = DEFAULT_DASHBOARD_URL,
    email: str | None = None,
    name: str | None = None,
    domains: list[str] | None = None,
    location: str | None = None,
) -> str:
    """Build a share link that pre-fills a friend's signup form.

    Only non-empty, validated values are included: ``email`` becomes the
    referrer shown on the friend's register tab, ``name`` the referrer's
    name, ``domains`` the pre-selected categories (restricted to
    :data:`KNOWN_DOMAINS`) and ``location`` the referrer's city.
    """
    params: list[str] = []
    if email:
        params.append(f"invite={quote(email.strip())}")
    if name:
        params.append(f"ref={quote(name.strip())}")
    if domains:
        clean = [
            d.strip().lower() for d in domains if d.strip().lower() in KNOWN_DOMAINS
        ]
        if clean:
            params.append("domains=" + quote(",".join(clean)))
    if location:
        params.append(f"loc={quote(location.strip())}")
    url = base_url.rstrip("/") + "/"
    return url + ("?" + "&".join(params) if params else "")


def parse_invite_params(raw: dict) -> dict:
    """Normalize raw query params (values may be str or list[str]).

    Returns a dict with only validated keys:

    - ``invite`` — the referrer's email (must look like an email)
    - ``ref`` — the referrer's name
    - ``location`` — the referrer's city
    - ``domains`` — a list restricted to :data:`KNOWN_DOMAINS`; ``["all"]``
      when the param was present but nothing matched
    """

    def first(key: str) -> str | None:
        value = raw.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    def list_values(key: str) -> list[str]:
        """All values for a param — lists stay whole, strings split on commas."""
        value = raw.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                parts.extend(str(item).split(","))
        else:
            parts = str(value).split(",")
        return [p.strip().lower() for p in parts if p.strip()]

    result: dict = {}
    invite = first("invite")
    if invite and "@" in invite:
        result["invite"] = invite
    ref = first("ref")
    if ref:
        result["ref"] = ref
    location = first("loc")
    if location:
        result["location"] = location
    domains_raw = list_values("domains")
    if domains_raw:
        picked = [d for d in domains_raw if d in KNOWN_DOMAINS]
        result["domains"] = picked if picked else ["all"]
    return result


# Characters with meaning in Streamlit/CommonMark — stripped from the
# referrer text so a crafted invite URL can't inject markdown/HTML.
_MARKDOWN_CHARS = frozenset("`*_~[]()<>#!\\|{}=")


def _plain(value: str) -> str:
    """Strip markdown-significant characters from untrusted query text."""
    return "".join(ch for ch in value if ch not in _MARKDOWN_CHARS).strip()


def count_referrals(users: list, referrer_email: str | None) -> int:
    """How many accounts signed up through a referrer's invite link.

    Matches on the lowercased ``referred_by`` field the API stores at
    registration; ``None``/empty referrer always returns 0, and the
    referrer's own account is never counted (no self-referrals).
    """
    if not referrer_email:
        return 0
    target = referrer_email.strip().lower()
    return sum(
        1
        for u in users
        if str(u.get("email") or "").strip().lower() != target
        and str(u.get("referred_by") or "").lower() == target
    )


def team_rows(users: list, me_email: str | None = None) -> list[dict]:
    """Shape the member directory for display (newest first, me flagged).

    Each row: ``name``, ``email``, ``location``, ``domains`` (raw keys),
    ``created_at`` (ISO), ``is_me`` and ``referred_by_me`` booleans.
    """
    me = (me_email or "").strip().lower()
    rows: list[dict] = []
    for u in users:
        email = str(u.get("email") or "")
        referred = str(u.get("referred_by") or "").lower()
        rows.append(
            {
                "name": str(u.get("name") or ""),
                "email": email,
                "location": str(u.get("location") or "—"),
                "domains": u.get("domains") or [],
                "created_at": u.get("created_at"),
                "is_me": bool(me and email.lower() == me),
                "referred_by_me": bool(me and referred == me),
            }
        )
    rows.sort(
        key=lambda r: (r["created_at"] is None, str(r["created_at"] or "")),
        reverse=True,
    )
    return rows


def invite_caption(invite: dict) -> str | None:
    """One-line caption for the register tab, or None when no invite.

    Example: ``"Invited by Parthasarathi — security"``. The referrer text
    is sanitized (markdown characters stripped) before embedding.
    """
    if not invite:
        return None
    referrer = _plain(invite.get("ref") or "") or _plain(invite.get("invite") or "")
    domains = invite.get("domains") or []
    if not referrer and not domains:
        return None
    parts = [f"Invited by **{referrer}**"] if referrer else ["Welcome!"]
    if domains and "all" not in domains:
        parts.append(", ".join(domains))
    return " · ".join(parts)
