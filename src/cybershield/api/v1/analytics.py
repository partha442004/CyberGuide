"""
Analytics API Router

Endpoints for skill trends, salary insights, and predictions.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from cybershield.dependencies import get_company_repository, get_skill_repository
from cybershield.repositories.company_repository import CompanyRepository
from cybershield.repositories.skill_repository import SkillRepository
from cybershield.schemas.analytics import MarketInsight

router = APIRouter()


@router.get("/skills/trending", response_model=List[dict])
async def get_trending_skills(
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(10, ge=1, le=50),
    repo: SkillRepository = Depends(get_skill_repository),
):
    """Get trending skills based on recent job postings."""
    trends = await repo.get_trending_skills(days=days, limit=limit)
    return trends


@router.get("/skills/market", response_model=List[dict])
async def get_skill_market_data(
    repo: SkillRepository = Depends(get_skill_repository),
):
    """Get market data for all skills."""
    data = await repo.get_skill_market_data()
    return data


@router.get("/skills/{skill_id}/trends", response_model=List[dict])
async def get_skill_trends(
    skill_id: str,
    months: int = Query(12, ge=1, le=60),
    repo: SkillRepository = Depends(get_skill_repository),
):
    """Get historical trend data for a skill."""
    trends = await repo.get_skill_trends(skill_id=skill_id, months=months)
    return trends


@router.get("/companies/top-hiring", response_model=List[dict])
async def get_top_hiring_companies(
    limit: int = Query(10, ge=1, le=50),
    country: Optional[str] = None,
    company_repo: CompanyRepository = Depends(get_company_repository),
):
    """Get top companies by job count."""
    companies = await company_repo.get_top_hiring_companies(limit=limit, country=country)
    return companies


@router.get("/insights/market", response_model=MarketInsight)
async def get_market_insights(
    repo: SkillRepository = Depends(get_skill_repository),
):
    """Get comprehensive market insights."""
    skill_data = await repo.get_skill_market_data()
    trending = await repo.get_trending_skills(days=30, limit=10)

    return {
        "total_skills_tracked": len(skill_data),
        "top_demanding_skills": [s["skill"].name for s in skill_data[:10]],
        "trending_skills": [t["skill"].name for t in trending],
        "market_health": "active",  # Placeholder for more complex analysis
    }
