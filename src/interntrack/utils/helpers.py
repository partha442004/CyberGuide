"""
Utility functions for InternTrack.
"""

from datetime import UTC, datetime


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


def location_matches(job_loc: str, user_loc: str) -> bool:
    """Fuzzy location match with synonyms (Bangalore ↔ Bengaluru, ...).

    Both arguments should be lowercased. True when the user's preferred
    city appears in the job's location string, or a known synonym does —
    so a "Bengaluru" preference matches a "Bangalore, Karnataka" posting
    and the same posting matches a "Hyderabad" user's filter only when it
    actually mentions Hyderabad. This is the single source of truth shared
    by the instant alerts, the digest builders and the report filter.
    """
    if not job_loc or not user_loc:
        return False
    if user_loc in job_loc:
        return True
    for canonical, alts in _LOCATION_SYNONYMS.items():
        if user_loc == canonical and any(_alt_in(alt, job_loc) for alt in alts):
            return True
        if user_loc in alts and canonical in job_loc:
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
