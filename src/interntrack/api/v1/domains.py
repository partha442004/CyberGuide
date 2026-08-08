"""
Domain-specific job listing endpoints.

Provides focused views for /cybersecurity, /development, /data, etc.
with tailored filters, trending skills, and salary insights per domain.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Job
from interntrack.utils.helpers import job_urgency, skill_taxonomy

router = APIRouter()

# Domain definitions with display metadata
DOMAINS = {
    "cybersecurity": {
        "label": "Cybersecurity",
        "icon": "\U0001f6e1\ufe0f",
        "color": "#ef4444",
        "description": "Security analyst, VAPT, SOC, penetration testing jobs",
        "keywords": [
            "security",
            "cyber",
            "soc",
            "vapt",
            "penetration",
            "firewall",
            "siem",
            "incident",
            "threat",
            "vulnerability",
            "owasp",
            "nmap",
            "metasploit",
            "burp",
            "ctf",
            "forensic",
            # Web-app + offensive security terms so SQLi/XSS/exploit jobs
            # land in the Cybersecurity category instead of Development.
            # Kept deliberately multi-character: ``_classify_job`` does a
            # plain substring test, so short terms like ``ids`` would
            # over-match inside unrelated words.
            "sqli",
            "sql injection",
            "xss",
            "csrf",
            "ssrf",
            "exploit",
            "malware",
            "ransomware",
            "phishing",
            "devsecops",
            "appsec",
            "red team",
            "blue team",
            "security analyst",
            "security engineer",
            "security operations",
            "threat hunting",
            "incident response",
            "malware analysis",
            "bug bounty",
            "cve",
            "waf",
            "encryption",
            "cryptography",
            "zero trust",
            "iso 27001",
            "grc",
            "osint",
            "cloud security",
            "network security",
            "endpoint security",
            "digital forensics",
            "infosec",
        ],
    },
    "development": {
        "label": "Development",
        "icon": "\U0001f4bb",
        "color": "#3b82f6",
        "description": "Software engineering, full-stack, backend, frontend jobs",
        "keywords": [
            "developer",
            "engineer",
            "python",
            "javascript",
            "react",
            "backend",
            "frontend",
            "fullstack",
            "api",
            "software",
            "coding",
            "programming",
            "node",
            "java",
            "golang",
            "rust",
        ],
    },
    "data": {
        "label": "Data & AI",
        "icon": "\U0001f9e0",
        "color": "#8b5cf6",
        "description": "Data science, ML engineering, analytics jobs",
        "keywords": [
            "data",
            "machine learning",
            "ai",
            "analytics",
            "science",
            "tensorflow",
            "pytorch",
            "nlp",
            "vision",
            "engineering",
            "etl",
            "pipeline",
            "model",
            "training",
            "ml",
            "deep learning",
        ],
    },
    "devops": {
        "label": "DevOps & Cloud",
        "icon": "\u2601\ufe0f",
        "color": "#06b6d4",
        "description": "Infrastructure, SRE, cloud, platform engineering jobs",
        "keywords": [
            "devops",
            "cloud",
            "infrastructure",
            "sre",
            "platform",
            "docker",
            "kubernetes",
            "terraform",
            "aws",
            "azure",
            "gcp",
            "ci/cd",
            "jenkins",
            "monitoring",
            "linux",
            "ansible",
        ],
    },
    "internships": {
        "label": "Internships",
        "icon": "\U0001f393",
        "color": "#22c55e",
        "description": "Internship and fresher positions across all domains",
        "keywords": [
            "intern",
            "internship",
            "fresher",
            "trainee",
            "graduate",
            "entry level",
            "junior",
            "apprentice",
        ],
    },
    "startups": {
        "label": "Startups",
        "icon": "\U0001f680",
        "color": "#f59e0b",
        "description": "Fast-growing startup jobs from Wellfound and more",
        "keywords": [
            "startup",
            "early stage",
            "series a",
            "series b",
            "founding",
            "growth",
            "wellfound",
            "angellist",
        ],
    },
}


def _classify_job(title: str, description: str | None, tags: list | None) -> list[str]:
    """Classify a job into one or more domains."""
    text = f"{title} {description or ''} {' '.join(tags or [])}".lower()
    matched = []
    for domain, meta in DOMAINS.items():
        for kw in meta["keywords"]:
            if kw in text:
                matched.append(domain)
                break
    return matched if matched else ["development"]


@router.get("/list")
async def list_domains():
    """List all available domains with metadata."""
    return {
        "domains": [
            {
                "key": k,
                "label": v["label"],
                "icon": v["icon"],
                "color": v["color"],
                "description": v["description"],
            }
            for k, v in DOMAINS.items()
        ]
    }


@router.get("/{domain}")
async def domain_jobs(
    domain: str,
    location: str | None = None,
    remote_only: bool = False,
    min_salary: int | None = None,
    sort: str = "newest",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get jobs filtered by domain with smart classification.

    Args:
        domain: One of cybersecurity, development, data, devops, internships, startups
        location: Filter by location (substring match)
        remote_only: Only remote jobs
        min_salary: Minimum salary filter
        sort: newest, oldest, salary_high, salary_low
        limit: Max results (up to 200)
        offset: Pagination offset
    """
    if domain not in DOMAINS:
        return {
            "error": f"Unknown domain: {domain}. Use /domains/list for valid domains."
        }

    meta = DOMAINS[domain]

    # Build query - get all active jobs and classify in Python
    query = select(Job).where(Job.is_active == True)  # noqa: E712
    result = await db.execute(query)
    all_jobs = result.scalars().all()

    # Classify and filter
    matched_jobs = []
    for job in all_jobs:
        job_domains = _classify_job(
            str(job.title), str(job.description or ""), list(job.tags or [])
        )
        if domain in job_domains:
            # Apply filters
            if (
                location
                and job.location
                and location.lower() not in job.location.lower()
            ):
                continue
            if remote_only and not job.is_remote:
                continue
            if min_salary and (job.salary_max or 0) < min_salary:
                continue
            matched_jobs.append(job)

    # Sort
    if sort == "newest":
        matched_jobs.sort(
            key=lambda j: j.created_at or j.posted_at or j.first_seen_at or "",
            reverse=True,
        )
    elif sort == "oldest":
        matched_jobs.sort(
            key=lambda j: j.created_at or j.posted_at or j.first_seen_at or ""
        )
    elif sort == "salary_high":
        matched_jobs.sort(key=lambda j: j.salary_max or 0, reverse=True)
    elif sort == "salary_low":
        matched_jobs.sort(key=lambda j: j.salary_min or 0)

    # Add urgency badges
    job_dicts = []
    for job in matched_jobs[offset : offset + limit]:
        urgency = job_urgency(job.posted_at, job.first_seen_at, job.is_active)
        job_dicts.append(
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "source": job.source.value if job.source else "unknown",
                "is_remote": job.is_remote,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "posted_at": str(job.posted_at) if job.posted_at else None,
                "urgency": urgency,
                "domain": domain,
                "domain_label": meta["label"],
                "domain_icon": meta["icon"],
                "domain_color": meta["color"],
            }
        )

    # Salary stats
    salaries = [j.salary_max for j in matched_jobs if j.salary_max and j.salary_max > 0]

    return {
        "domain": domain,
        "meta": meta,
        "total": len(matched_jobs),
        "jobs": job_dicts,
        "salary_stats": {
            "min": min(salaries) if salaries else None,
            "max": max(salaries) if salaries else None,
            "avg": round(sum(salaries) / len(salaries)) if salaries else None,
            "count": len(salaries),
        },
        "filters": {
            "location": location,
            "remote_only": remote_only,
            "min_salary": min_salary,
            "sort": sort,
        },
    }


@router.get("/{domain}/trending-skills")
async def trending_skills(
    domain: str,
    db: AsyncSession = Depends(get_db),
):
    """Get trending skills for a specific domain based on job listings."""
    if domain not in DOMAINS:
        return {"error": f"Unknown domain: {domain}"}

    # Get taxonomy keywords for this domain
    taxonomy = skill_taxonomy()
    domain_config = taxonomy.get(domain, {})
    domain_keywords = domain_config.get("keywords", [])

    # Count keyword occurrences in job descriptions
    query = select(Job).where(Job.is_active == True)  # noqa: E712
    result = await db.execute(query)
    all_jobs = result.scalars().all()

    skill_counts: dict[str, int] = {}
    for job in all_jobs:
        job_domains = _classify_job(
            str(job.title), str(job.description or ""), list(job.tags or [])
        )
        if domain not in job_domains:
            continue
        text = f"{job.title} {job.description or ''}".lower()
        for kw in domain_keywords:
            if kw in text:
                skill_counts[kw] = skill_counts.get(kw, 0) + 1

    # Sort by count
    trending = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "domain": domain,
        "trending": [{"skill": skill, "count": count} for skill, count in trending],
    }
