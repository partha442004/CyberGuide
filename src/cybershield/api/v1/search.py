"""
Search API Router

Advanced full-text search for job listings using Elasticsearch.
Falls back to database search when Elasticsearch is unavailable.
"""

from typing import List, Optional

from fastapi import APIRouter, Query

from cybershield.services import elasticsearch_service as es

router = APIRouter()


@router.get("/")
async def search_jobs(
    q: Optional[str] = Query(None, description="Full-text search query"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    country: Optional[str] = Query(None, description="Filter by country"),
    location: Optional[str] = Query(None, description="Filter by location"),
    skills: Optional[List[str]] = Query(None, description="Filter by required skills"),
    job_type: Optional[str] = Query(None, description="Filter by job type (full_time, part_time, contract)"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    is_remote: Optional[bool] = Query(None, description="Filter remote jobs only"),
    min_salary: Optional[float] = Query(None, description="Minimum salary filter"),
    max_salary: Optional[float] = Query(None, description="Maximum salary filter"),
    sort_by: str = Query("_score", description="Sort field (relevance, posting_date, salary_min)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    Advanced job search with full-text queries, filters, and facets.

    When Elasticsearch is available:
    - Full-text search across title, description, company, and skills
    - Fuzzy matching for typos
    - Faceted aggregations for company, country, skills, and salary stats

    When Elasticsearch is unavailable:
    - Falls back to database text search
    """
    # Validate sort field to prevent ES errors
    allowed_sort_fields = {"_score", "posting_date", "salary_min", "created_at", "title.keyword"}
    if sort_by not in allowed_sort_fields:
        sort_by = "_score"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    result = await es.search_jobs(
        query=q,
        company=company,
        country=country,
        location=location,
        skills=skills,
        job_type=job_type,
        experience_level=experience_level,
        is_remote=is_remote,
        min_salary=min_salary,
        max_salary=max_salary,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )

    return {
        "items": result["results"],
        "total": result["total"],
        "skip": skip,
        "limit": limit,
        "source": result["source"],
        "aggregations": result.get("aggregations", {}),
    }


@router.get("/status")
async def search_status():
    """Check Elasticsearch connectivity and index statistics."""
    stats = await es.get_index_stats()
    return {
        "elasticsearch_available": es.is_available(),
        "index_stats": stats,
    }
