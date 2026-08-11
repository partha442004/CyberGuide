"""
Salary Insights API — salary statistics per domain, location, experience level.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Job

router = APIRouter()


def _compute_benchmark_rows(jobs) -> list[dict[str, Any]]:
    """Bucket active salaried jobs into (domain, city) benchmark rows.

    Shared by the API endpoint and the weekly digest's salary insight so
    the numbers can never drift between the dashboard and notifications.
    """
    from statistics import median

    buckets: dict[tuple[str, str], list[int]] = {}
    for job in jobs:
        lo = job.salary_min
        hi = job.salary_max
        value = None
        if lo and hi:
            value = int((lo + hi) / 2)
        elif lo:
            value = int(lo)
        elif hi:
            value = int(hi)
        if not value or value <= 0:
            continue
        title = str(job.title or "")
        desc = str(job.description or "")
        domain = _classify_domain(title, desc)
        loc = str(job.location or "Remote").strip()
        # Collapse long location strings to the leading city token.
        city = loc.split(",")[0].strip()[:40] or "Remote"
        buckets.setdefault((domain, city), []).append(value)

    rows: list[dict[str, Any]] = []
    for (domain, city), values in buckets.items():
        rows.append(
            {
                "domain": domain,
                "city": city,
                "count": len(values),
                "median": int(median(values)),
                "average": int(sum(values) / len(values)),
                "min": min(values),
                "max": max(values),
                "currency": "INR" if max(values) >= 100000 else "USD",
            }
        )
    rows.sort(key=lambda r: (-r["count"], r["domain"], r["city"]))
    return rows


@router.get("/benchmarks")
async def salary_benchmarks(
    db: AsyncSession = Depends(get_db),
):
    """Role × city salary benchmark from real stored postings.

    Groups active jobs that carry a salary by (domain, city) and returns
    median / average / min / max / count per bucket, plus the overall top
    cities — so a user can answer "what does a SOC Analyst in Bangalore
    actually pay?" from live data.
    """
    from sqlalchemy import select

    query = select(Job).where(Job.is_active == True)  # noqa: E712
    result = await db.execute(query)
    rows = _compute_benchmark_rows(result.scalars().all())

    from collections import Counter

    city_counts = Counter(r["city"] for r in rows)
    return {
        "rows": rows[:120],
        "total_buckets": len(rows),
        "top_cities": [
            {"city": c, "buckets": n} for c, n in city_counts.most_common(8)
        ],
    }


async def salary_benchmark_for(session, domain: str, city: str) -> dict | None:
    """Best benchmark row for a domain + city, or ``None`` when no data.

    Prefers an exact city row, then a synonym match (Bangalore vs
    Bengaluru…), then a Remote-only row for the domain — so the weekly
    digest's salary insight always reflects live postings. Never raises.
    """
    try:
        from sqlalchemy import select

        from interntrack.utils.helpers import location_matches

        query = select(Job).where(Job.is_active == True)  # noqa: E712
        result = await session.execute(query)
        rows = _compute_benchmark_rows(result.scalars().all())
    except Exception:  # noqa: BLE001, S110 - insight must never break the digest
        return None
    domain_rows = [r for r in rows if r["domain"] == domain]
    if not domain_rows:
        return None
    city_key = str(city or "").strip()
    if city_key:
        for row in domain_rows:
            if row["city"].lower() == city_key.lower():
                return row
        for row in domain_rows:
            if location_matches(row["city"].lower(), city_key.lower()):
                return row
    for row in domain_rows:
        if row["city"].lower() == "remote":
            return row
    return None


def _classify_domain(title: str, description: str | None) -> str:
    """Classify job into a domain based on title/description."""
    text = f"{title} {description or ''}".lower()

    if any(
        kw in text
        for kw in ["security", "cyber", "soc", "vapt", "penetration", "firewall"]
    ):
        return "security"
    if any(
        kw in text
        for kw in ["data", "ml", "machine learning", "ai", "analytics", "science"]
    ):
        return "data"
    if any(
        kw in text for kw in ["devops", "cloud", "infrastructure", "sre", "platform"]
    ):
        return "devops"
    if any(kw in text for kw in ["design", "ui", "ux", "figma", "graphic"]):
        return "design"
    return "development"


@router.get("/overview")
async def salary_overview(
    domain: str | None = None,
    location: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get salary overview with statistics."""
    query = select(Job).where(Job.is_active == True)  # noqa: E712
    if domain:
        query = query.where(Job.tags.contains([domain]))

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Filter by location if provided
    if location:
        jobs = [j for j in jobs if location.lower() in (j.location or "").lower()]

    # Collect salary data
    salaries = []
    by_domain: dict[str, list] = {}
    by_location: dict[str, list] = {}

    for job in jobs:
        if job.salary_max and job.salary_max > 0:
            salaries.append(job.salary_max)
            domain_key = _classify_domain(str(job.title), str(job.description or ""))
            by_domain.setdefault(domain_key, []).append(job.salary_max)
            loc = str(job.location or "Remote")
            by_location.setdefault(loc, []).append(job.salary_max)

    if not salaries:
        return {
            "message": "No salary data available",
            "total_jobs": len(jobs),
            "jobs_with_salary": 0,
        }

    # Calculate statistics
    def calc_stats(values):
        if not values:
            return None
        return {
            "min": min(values),
            "max": max(values),
            "avg": round(sum(values) / len(values)),
            "median": sorted(values)[len(values) // 2],
            "count": len(values),
        }

    # Domain breakdown
    domain_stats = {}
    for d, vals in sorted(by_domain.items(), key=lambda x: len(x[1]), reverse=True):
        domain_stats[d] = calc_stats(vals)

    # Location breakdown
    location_stats = {}
    for loc, vals in sorted(by_location.items(), key=lambda x: len(x[1]), reverse=True)[
        :10
    ]:
        location_stats[loc] = calc_stats(vals)

    return {
        "overall": calc_stats(salaries),
        "total_jobs": len(jobs),
        "jobs_with_salary": len(salaries),
        "by_domain": domain_stats,
        "by_location": location_stats,
        "currency": "USD",
    }


@router.get("/domain/{domain}")
async def domain_salary(
    domain: str,
    location: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get salary insights for a specific domain."""
    query = select(Job).where(Job.is_active == True)  # noqa: E712
    result = await db.execute(query)
    all_jobs = result.scalars().all()

    # Filter by domain
    domain_jobs = [
        j
        for j in all_jobs
        if _classify_domain(str(j.title), str(j.description or "")) == domain
    ]

    # Filter by location
    if location:
        domain_jobs = [
            j for j in domain_jobs if location.lower() in (j.location or "").lower()
        ]

    # Collect salary data
    salaries = [j.salary_max for j in domain_jobs if j.salary_max and j.salary_max > 0]

    if not salaries:
        return {
            "domain": domain,
            "message": f"No salary data for {domain}",
            "total_jobs": len(domain_jobs),
        }

    # Top companies by salary
    company_salaries: dict[str, list] = {}
    for job in domain_jobs:
        if job.salary_max and job.salary_max > 0:
            company_salaries.setdefault(str(job.company), []).append(job.salary_max)

    top_companies = sorted(
        company_salaries.items(),
        key=lambda x: max(x[1]),
        reverse=True,
    )[:10]

    return {
        "domain": domain,
        "location": location,
        "overall": {
            "min": min(salaries),
            "max": max(salaries),
            "avg": round(sum(salaries) / len(salaries)),
            "median": sorted(salaries)[len(salaries) // 2],
            "count": len(salaries),
        },
        "total_jobs": len(domain_jobs),
        "top_companies": [
            {
                "company": c,
                "avg_salary": round(sum(s) / len(s)),
                "max_salary": max(s),
                "count": len(s),
            }
            for c, s in top_companies
        ],
    }


@router.get("/compare")
async def compare_salaries(
    domains: str = Query(description="Comma-separated domains to compare"),
    db: AsyncSession = Depends(get_db),
):
    """Compare salaries across multiple domains."""
    domain_list = [d.strip() for d in domains.split(",") if d.strip()]

    query = select(Job).where(Job.is_active == True)  # noqa: E712
    result = await db.execute(query)
    all_jobs = result.scalars().all()

    comparison = {}
    for domain in domain_list:
        domain_jobs = [
            j
            for j in all_jobs
            if _classify_domain(str(j.title), str(j.description or "")) == domain
        ]
        salaries = [
            j.salary_max for j in domain_jobs if j.salary_max and j.salary_max > 0
        ]

        if salaries:
            comparison[domain] = {
                "min": min(salaries),
                "max": max(salaries),
                "avg": round(sum(salaries) / len(salaries)),
                "count": len(salaries),
                "job_count": len(domain_jobs),
            }
        else:
            comparison[domain] = {
                "message": "No salary data",
                "job_count": len(domain_jobs),
            }

    return {
        "domains": domain_list,
        "comparison": comparison,
    }
