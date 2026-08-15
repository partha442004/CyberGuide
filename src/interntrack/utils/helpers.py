"""
Utility functions for InternTrack.
"""

import re
from datetime import UTC, datetime
from html import (
    unescape,
)  # TLDs (and the bare single-label domain) that can never receive mail.

# Sending From these guarantees SPF/DKIM failure and a one-way ticket to
# the Spam folder (the default EMAIL_FROM was "noreply@interntrack.local").
# Only the final label is checked, so real routable domains like
# ``test.com``, ``myapp.testing.com`` or ``foo.localdomain.com`` are never
# mistaken for the reserved ``.test`` / ``.local`` TLDs.
_NON_ROUTABLE_TLDS = {"local", "invalid", "example", "test", "localhost"}


def email_domain(address: str) -> str:
    """Lowercased domain of an address, or empty when unparseable."""
    m = re.search(r"@([^@>\s]+)", address)
    return m.group(1).strip(".").lower() if m else ""


def _domain_is_routable(domain: str) -> bool:
    """True when the domain is a real, deliverable one."""
    if not domain:
        return False
    tld = domain.rsplit(".", 1)[-1].lower()
    return tld not in _NON_ROUTABLE_TLDS


def deliverable_from_email(
    from_email: str | None,
    smtp_user: str | None,
) -> str:
    """A From address that can actually be delivered from.

    The config default ``noreply@interntrack.local`` is a non-routable
    domain — Gmail flags such mail as spam because SPF/DKIM can never
    authenticate it. When the configured From is missing or uses a
    non-routable domain, fall back to the authenticated SMTP account
    (e.g. the real Gmail address), whose domain carries valid SPF/DKIM
    records. Never raises; the last resort is a bare "InternTrack".
    """
    raw = str(from_email or "").strip()
    if raw and _domain_is_routable(email_domain(raw)):
        return raw
    fallback = str(smtp_user or "").strip()
    if fallback and "@" in fallback:
        return f"InternTrack <{fallback}>"
    return "InternTrack"


def html_to_text(html_body: str) -> str:
    """Crude but safe HTML -> plain text (for the multipart alternative)."""
    text = re.sub(r"<style[^>]*>.*?</style>", " ", html_body, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>\s*", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>\s*", "\n", text, flags=re.I)
    # Keep link URLs alive in the plain-text part — a stripped "Apply"
    # button with no URL is useless in text-only clients.
    text = re.sub(
        r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        r"\2 (\1)",
        text,
        flags=re.S | re.I,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def utcnow():
    """Return the current UTC time as a naive datetime (for DB storage)."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert an aware datetime to naive UTC, or return naive as-is."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


# City-name synonyms used by :func:`location_matches` so a preference like
# "Bangalore" still matches postings written as "Bengaluru" (and vice-versa).
# Short aliases (e.g. "ncr") are matched with word boundaries by
# :func:`location_matches` so "Encryption Corp" never passes a Delhi filter.
_LOCATION_SYNONYMS = {
    "bangalore": ["bengaluru", "bengalore"],
    "bengaluru": ["bangalore", "bengalore"],
    "mumbai": ["bombay"],
    "bombay": ["mumbai"],
    "delhi": ["new delhi", "delhi ncr", "ncr"],
    "hyderabad": ["secunderabad"],
}

# Phrases meaning "any Indian city is fine". A user who sets their
# preferred location to "All India" (optionally alongside specific cities)
# matches any posting that mentions India or a major Indian city.
_INDIA_WIDE_PHRASES = (
    "all india",
    "anywhere in india",
    "across india",
    "pan india",
    "india wide",
    "throughout india",
    "india",
)

# Major Indian cities used to recognise an Indian posting when its location
# string lacks the literal word "India" (e.g. just "Bengaluru").
_INDIAN_CITIES = (
    "bangalore",
    "bengaluru",
    "chennai",
    "madras",
    "mumbai",
    "bombay",
    "delhi",
    "new delhi",
    "hyderabad",
    "secunderabad",
    "pune",
    "kolkata",
    "calcutta",
    "ahmedabad",
    "gurgaon",
    "gurugram",
    "noida",
    "jaipur",
    "kochi",
    "cochin",
    "coimbatore",
    "indore",
    "lucknow",
    "nagpur",
    "surat",
    "visakhapatnam",
    "vijayawada",
    "mysore",
    "mysuru",
    "thiruvananthapuram",
    "trivandrum",
    "madurai",
    "kanpur",
    "chandigarh",
    "bhubaneswar",
    "guwahati",
    "amritsar",
    "varanasi",
    "ludhiana",
    "raipur",
    "patna",
    "ranchi",
    "mangalore",
    "mangaluru",
    "bhopal",
    "dehradun",
    "nashik",
    "nasik",
    "agra",
    "tiruchirappalli",
    "tirupur",
    "salem",
    "erode",
    "nellore",
    "kakinada",
    "vadodara",
    "rajkot",
    "gwalior",
    "jabalpur",
    "jamshedpur",
    "siliguri",
    "puducherry",
    "panaji",
    "shimla",
    "udupi",
)


def _is_india_wide(pref: str) -> bool:
    """True when a location preference means 'any Indian city is fine'."""
    return pref.strip().lower() in _INDIA_WIDE_PHRASES


def _is_indian_job(job_loc: str) -> bool:
    """True when a location string points at India (country or city name).

    The country name is matched with word boundaries so "Indiana, USA" (a
    US state) can never pass an all-India filter — only "India" as a
    standalone word does (e.g. "Bengaluru, Karnataka, India").
    """
    if not job_loc:
        return False
    lower = job_loc.lower()
    if _alt_in("india", lower):
        return True
    return any(_alt_in(city, lower) for city in _INDIAN_CITIES)


def location_matches(job_loc: str, user_loc: str) -> bool:
    """Fuzzy location match with synonyms (Bangalore ↔ Bengaluru, ...).

    Both arguments should be lowercased. ``user_loc`` may list several
    cities ("bangalore, hyderabad" or "bangalore/hyderabad"): a job
    matches when it mentions ANY of them. An "all india" / "india"
    preference matches any posting that mentions India or a major Indian
    city, so a pan-India user never misses a Pune or Mumbai role. True
    when a preferred city appears in the job's location string, or a
    known synonym does — so a "Bengaluru" preference matches a
    "Bangalore, Karnataka" posting and the same posting matches a
    "Hyderabad" user's filter only when it actually mentions Hyderabad.
    This is the single source of truth shared by the instant alerts, the
    digest builders and the report filter.
    """
    if not job_loc or not user_loc:
        return False
    for part in re.split(r"\s*[,/]\s*", user_loc):
        if not part:
            continue
        if _is_india_wide(part):
            if _is_indian_job(job_loc):
                return True
            continue
        if _single_location_matches(job_loc, part):
            return True
    return False


def _single_location_matches(job_loc: str, city: str) -> bool:
    """One-city match: the city (or a known synonym) appears in job_loc."""
    if city in job_loc:
        return True
    for canonical, alts in _LOCATION_SYNONYMS.items():
        if city == canonical and any(_alt_in(alt, job_loc) for alt in alts):
            return True
        if city in alts and canonical in job_loc:
            return True
    return False


def _alt_in(alt: str, job_loc: str) -> bool:
    """Word-boundary match for a synonym inside a location string.

    Multi-word aliases ("new delhi") match as-is; short ones like "ncr"
    must appear as a standalone token so "Enncr[yption]"-style false
    positives can never slip a wrong-city job past a location filter.
    """
    import re

    return bool(re.search(rf"(?<![a-z0-9]){re.escape(alt)}(?![a-z0-9])", job_loc))


# Location substrings that mean the role can be done from anywhere. Used by
# :func:`is_remote_location` so a user who opts into remote work gets WFH /
# fully-remote / "anywhere" listings alongside their preferred city instead
# of them being silently dropped by the city-only filter.
_REMOTE_MARKERS = (
    "remote",
    "work from home",
    "wfh",
    "anywhere",
    "virtual",
    "telecommute",
    "home based",
    "home-based",
    "hybrid - remote",
    "remote - hybrid",
)


def is_remote_location(job_loc: str) -> bool:
    """True when a job's location string means remote / work-from-home work.

    Case-insensitive substring match against a fixed marker list ("remote",
    "work from home", "wfh", "anywhere", "virtual", "telecommute", ...).
    "Hybrid" on its own is NOT remote (the employer still wants you in the
    office some days), but explicitly "remote"-titled hybrid postings are.
    """
    if not job_loc:
        return False
    lower = job_loc.lower()
    return any(marker in lower for marker in _REMOTE_MARKERS)


def location_allows(job_loc: str, user_loc: str, include_remote: bool = True) -> bool:
    """Whether a job's location fits a user's preferred city (+ optional remote).

    Single source of truth for the per-user location gate shared by the
    daily digest, the instant alerts and the report filter. ``user_loc`` is
    the user's preferred city (lowercased); ``include_remote`` adds remote /
    WFH / anywhere listings on top of the city match, so a Bangalore user
    who opts in also receives fully-remote security roles.
    """
    if location_matches(job_loc, user_loc):
        return True
    return bool(include_remote and is_remote_location(job_loc))


# Title/description markers that reveal seniority when a job's experience
# level was never parsed (AI classification unavailable). Matched as whole
# words so "internal" never reads as "intern" and "staffing" never as
# "staff". Used only to catch obvious senior postings in fresher mode.
_SENIOR_LEVEL_MARKERS = (
    "senior",
    "sr",
    "lead",
    "principal",
    "architect",
    "director",
    "manager",
    "head of",
    "staff",
    "vp",
    "vice president",
    "executive",
)
_FRESHER_LEVEL_MARKERS = (
    "fresher",
    "entry level",
    "entry-level",
    "intern",
    "trainee",
    "apprentice",
    "graduate trainee",
)


def _detect_level_from_text(job) -> str | None:
    """Best-effort seniority guess for jobs with no parsed experience level.

    Senior/fresher role markers are applied to the TITLE only — a fresher
    description routinely mentions managers / senior engineers ("under the
    Security Manager"), so scanning it for role words would wrongly drop
    fresher jobs. The description is used only for years requirements
    ("8-13 years" / "5+ years" -> senior, 3 -> mid, 0-2 -> entry).
    Returns None when nothing is detected so the caller keeps the
    permissive default. Never raises.
    """
    try:
        if isinstance(job, dict):
            title = str(job.get("title") or "").lower()
            desc = str(job.get("description") or "")[:1000].lower()
        else:
            title = str(getattr(job, "title", None) or "").lower()
            desc = str(getattr(job, "description", None) or "")[:1000].lower()
        if any(_alt_in(m, title) for m in _SENIOR_LEVEL_MARKERS):
            return "senior"
        if any(_alt_in(m, title) for m in _FRESHER_LEVEL_MARKERS):
            return "entry"
        # Years requirements: "5-8 years", "8 to 13 years", "2+ years", ...
        m = re.search(r"(\d{1,2})\s*(?:-|–|to)\s*\d{1,2}\s*(?:years?|yrs)", desc)
        if not m:
            m = re.search(r"(\d{1,2})\s*\+?\s*(?:years?|yrs)", desc)
        if m:
            years = int(m.group(1))
            if years >= 4:
                return "senior"
            if years >= 3:
                return "mid"
            return "entry"
        return None
    except Exception:  # noqa: BLE001 - a bad text must never break a digest
        return None


def job_experience_ok(job, allowed_levels: list | None) -> bool:
    """Whether a job's experience level fits a user's allowed set.

    Single source of truth for the per-user experience gate shared by the
    daily digest, the instant alerts, the report filter and the closing-
    soon sweep. ``allowed_levels`` is a list of ExperienceLevel values
    (entry, junior, mid, senior, ...); an empty list / None means every
    level passes. Jobs whose level is parsed and out of scope are dropped.
    Jobs with no parsed level default to passing (an unspecified posting
    may still be fresher-friendly) unless the title/description clearly
    marks the role as senior/mid ("Senior Manager", "8-13 years"), in
    which case they are dropped in fresher mode too. Never raises.
    """
    if not allowed_levels:
        return True
    try:
        allowed = {str(x).strip().lower() for x in allowed_levels}
        # Accepts ORM Job rows and plain dicts (the closing-soon sweep maps
        # its rows to dicts before per-user filtering).
        if isinstance(job, dict):
            level = str(job.get("experience_level") or "").strip().lower()
        else:
            level = str(getattr(job, "experience_level", None) or "").strip().lower()
        if not level or level == "unknown":
            # Unparsed listing: keep by default, but catch obvious senior /
            # mid postings so fresher users never see them.
            detected = _detect_level_from_text(job)
            if detected in ("senior", "mid"):
                return detected in allowed
            return True
        # A parsed fresher/intern level is authoritative — it always passes
        # (a fresher description may still mention managers/senior roles).
        if level in ("fresher", "intern"):
            return True
        return level in allowed
    except Exception:  # noqa: BLE001 - a bad level must never break a digest
        return True


def job_urgency(posted_at, first_seen_at=None, is_active=True):
    """Compute job urgency badge based on age.

    Returns a dict with badge, label, color and days since posting.
    """
    now = utcnow()
    ref = posted_at or first_seen_at
    if ref is None:
        return {
            "badge": "unknown",
            "label": "Unknown",
            "color": "#94a3b8",
            "days": None,
        }
    age = (now - ref).days
    if not is_active:
        return {"badge": "expired", "label": "Expired", "color": "#ef4444", "days": age}
    if age <= 3:
        return {"badge": "fresh", "label": "Fresh", "color": "#22c55e", "days": age}
    if age <= 7:
        return {"badge": "recent", "label": "Recent", "color": "#3b82f6", "days": age}
    if age <= 20:
        return {
            "badge": "closing_soon",
            "label": "Closing Soon",
            "color": "#f59e0b",
            "days": age,
        }
    return {"badge": "stale", "label": "Stale", "color": "#ef4444", "days": age}


def skill_taxonomy():
    """Return the domain skill taxonomy for weighted match scoring."""
    return {
        "security": {
            "keywords": [
                "vulnerability assessment",
                "penetration testing",
                "vapt",
                "soc",
                "siem",
                "firewall",
                "ids",
                "ips",
                "waf",
                "owasp",
                "burp suite",
                "nmap",
                "metasploit",
                "nessus",
                "qualys",
                "cobalt strike",
                "red team",
                "blue team",
                "incident response",
                "threat hunting",
                "malware analysis",
                "forensics",
                "ctf",
                "bug bounty",
                "cve",
                "exploit",
                "security audit",
                "compliance",
                "iso 27001",
                "nist",
                "zero trust",
                "encryption",
                "cryptography",
                "pki",
                "cloud security",
                "aws security",
                "azure security",
                "devsecops",
                "sast",
                "dast",
                "sbom",
                # Web-app security: must sit before bare "sql" so a resume
                # listing SQLi is scored as security, not data/coding.
                "sqli",
                "sql injection",
                "sqlmap",
                "xss",
                "csrf",
                "ssrf",
                "idor",
                "authentication bypass",
                "grc",
                "osint",
                "dfir",
                "cissp",
                "ceh",
                "ethical hacking",
                "cybersecurity",
                "cyber security",
                "security operations",
                "threat intelligence",
            ],
            "bonus": 1.3,
        },
        "coding": {
            "keywords": [
                "python",
                "javascript",
                "typescript",
                "java",
                "c++",
                "golang",
                "rust",
                "react",
                "angular",
                "vue",
                "node.js",
                "fastapi",
                "django",
                "flask",
                "spring boot",
                "microservices",
                "rest api",
                "graphql",
                "docker",
                "kubernetes",
                "terraform",
                "ci/cd",
                "git",
                "sql",
                "nosql",
                "mongodb",
                "postgresql",
                "redis",
                "aws",
                "azure",
                "gcp",
                "linux",
                "bash",
                "automation",
            ],
            "bonus": 1.0,
        },
        "data": {
            "keywords": [
                "machine learning",
                "deep learning",
                "tensorflow",
                "pytorch",
                "pandas",
                "numpy",
                "scikit-learn",
                "data science",
                "data analysis",
                "data engineering",
                "etl",
                "airflow",
                "spark",
                "hadoop",
                "sql",
                "tableau",
                "power bi",
                "statistics",
                "r",
                "sas",
                "nlp",
                "computer vision",
                "neural network",
                "regression",
                "classification",
                "a/b testing",
                "data pipeline",
            ],
            "bonus": 1.0,
        },
        "devops": {
            "keywords": [
                "docker",
                "kubernetes",
                "terraform",
                "ansible",
                "jenkins",
                "github actions",
                "gitlab ci",
                "prometheus",
                "grafana",
                "elk stack",
                "datadog",
                "aws",
                "azure",
                "gcp",
                "linux",
                "bash",
                "python",
                "infrastructure",
                "cloud",
                "sre",
                "monitoring",
                "incident response",
                "load balancer",
                "nginx",
            ],
            "bonus": 1.0,
        },
        "design": {
            "keywords": [
                "figma",
                "sketch",
                "adobe xd",
                "ui design",
                "ux design",
                "user research",
                "wireframe",
                "prototype",
                "design system",
                "accessibility",
                "responsive design",
                "css",
                "html",
            ],
            "bonus": 1.0,
        },
    }


def _word_boundary_hit(skill: str, keyword: str) -> bool:
    """True when ``skill`` and ``keyword`` overlap as whole words.

    Plain substring checks are dangerously loose: the data keyword ``r``
    matches inside "cybersecurity", and ``sql`` matches inside a security
    resume's "sqli". Requiring word boundaries keeps those apart while
    still letting "sql injection" (keyword) match a "sql" skill and
    "penetration testing" match on both sides.
    """
    import re

    return bool(
        re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", skill)
        or re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", keyword)
    )


def match_score_v2(resume_skills, job_tags=None, job_description=""):
    """Weighted skill match scoring with domain bonuses.

    Args:
        resume_skills: list of skill strings from the user resume
        job_tags: list of tags/keywords from the job listing
        job_description: full job description text for additional matching

    Returns:
        dict with score (0-100), domain, matched_skills, reasoning
    """
    taxonomy = skill_taxonomy()
    resume_lower = [s.lower().strip() for s in resume_skills]
    job_tags = job_tags or []
    desc_lower = job_description.lower()

    best_domain = "coding"
    best_score = 0.0
    best_matches: list[str] = []

    for domain, config in taxonomy.items():
        domain_keywords = [k.lower() for k in config["keywords"]]
        bonus = config["bonus"]

        # Count direct matches (word-boundary aware)
        matched = []
        for skill in resume_lower:
            for keyword in domain_keywords:
                if _word_boundary_hit(skill, keyword):
                    matched.append(skill)
                    break

        # Bonus for domain mention in description
        desc_bonus = 0
        for kw in domain_keywords[:10]:  # top 10 high-signal keywords
            if kw in desc_lower:
                desc_bonus += 2

        # Calculate score
        if domain_keywords:
            raw = (len(matched) / max(len(domain_keywords), 1)) * 100
            raw += desc_bonus
            raw *= bonus
            score = min(raw, 100.0)
        else:
            score = 0.0

        if score > best_score:
            best_score = score
            best_domain = domain
            best_matches = matched

    return {
        "score": round(best_score, 1),
        "domain": best_domain,
        "matched_skills": best_matches,
        "reasoning": f"Matched {len(best_matches)} skills in {best_domain} domain",
    }


def format_datetime(dt, fmt="%Y-%m-%d %H:%M"):
    """Format datetime to string."""
    if dt:
        return dt.strftime(fmt)
    return "N/A"


def format_currency(amount, currency="USD"):
    """Format currency amount."""
    if amount is None:
        return "N/A"
    return f"${amount:,.2f} {currency}"


def truncate_text(text, max_length=100):
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def slugify(text):
    """Convert text to slug."""
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def generate_id():
    """Generate a unique ID."""
    from uuid import uuid4

    return str(uuid4())


def salary_band_txt(
    low: float | None, high: float | None, currency: str = "INR"
) -> str:
    """Compact median salary band ("₹8–12 LPA" / "$80k–100k"), or "".

    Pure formatter for the digest market snapshot: given the median low /
    high bounds of a company's posted salaries, render a short readable
    band. Unknown bounds return "". INR values >= 1L render as lakhs
    ("₹12 LPA"), smaller as thousands ("₹45K").
    """
    if low is None and high is None:
        return ""
    currency = str(currency or "INR").upper()
    symbol = "₹" if currency == "INR" else "$"

    def fmt(value: float) -> str:
        if currency == "INR" and value >= 100000:
            return f"{value / 100000:.1f}".rstrip("0").rstrip(".") + " LPA"
        if currency == "INR":
            return f"{value / 1000:.0f}K"
        return f"{value / 1000:.0f}k"

    if low is not None and high is not None and high > low:
        return f"{symbol}{fmt(low)}–{symbol}{fmt(high)}"
    if low is not None:
        return f"{symbol}{fmt(low)}"
    if high is not None:
        return f"{symbol}{fmt(high)}"
    return ""


def apply_token(user_id: str, job_id: str) -> str:
    """HMAC token authenticating one digest-email apply link.

    Binds ``user_id`` + ``job_id`` to the server secret, so only links we
    actually emailed can record an application. Never raises.
    """
    import hashlib
    import hmac

    from interntrack.config import get_settings

    secret = str(get_settings().secret_key).encode()
    message = f"{user_id}|{job_id}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_apply_token(user_id: str, job_id: str, token: str) -> bool:
    """Constant-time check of an apply-link token."""
    import hmac

    if not token:
        return False
    expected = apply_token(user_id, job_id)
    return hmac.compare_digest(expected, token)
