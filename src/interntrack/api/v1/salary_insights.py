"""
Salary Insights API — salary statistics per domain, location, experience level.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Job

router = APIRouter()


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
    by_domain = {}
    by_location = {}

    for job in jobs:
        if job.salary_max and job.salary_max > 0:
            salaries.append(job.salary_max)
            domain_key = _classify_domain(job.title, job.description)
            by_domain.setdefault(domain_key, []).append(job.salary_max)
            loc = job.location or "Remote"
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
        j for j in all_jobs if _classify_domain(j.title, j.description) == domain
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
    company_salaries = {}
    for job in domain_jobs:
        if job.salary_max and job.salary_max > 0:
            company_salaries.setdefault(job.company, []).append(job.salary_max)

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
            j for j in all_jobs if _classify_domain(j.title, j.description) == domain
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
