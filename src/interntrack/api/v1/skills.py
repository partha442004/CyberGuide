"""
Skills API endpoints.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.engines.classification import ClassificationEngine
from interntrack.repositories.skill_repository import SkillRepository
from interntrack.services.ai_service import AIService

router = APIRouter()


@router.get("/")
async def list_skills(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List skills with optional filters."""
    repo = SkillRepository(db)

    if search:
        skills = await repo.search_skills(search)
    elif category:
        from interntrack.domain.enums import SkillCategory
        skills = await repo.get_by_category(SkillCategory(category))
    else:
        skills = await repo.get_active_skills()

    return {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category.value,
                "difficulty_level": s.difficulty_level,
            }
            for s in skills
        ],
        "total": len(skills),
    }


@router.get("/demand")
async def get_skill_demand(
    db: AsyncSession = Depends(get_db),
):
    """Get skill demand from job listings."""
    engine = ClassificationEngine(db)
    return await engine.get_skill_demand()


@router.post("/match")
async def match_skills(
    job_skills: List[str],
    user_skills: List[str],
    db: AsyncSession = Depends(get_db),
):
    """Match job skills with user skills."""
    service = AIService(db)
    return await service.match_skills(job_skills, user_skills)


@router.get("/learning-path")
async def get_learning_path(
    current_skills: List[str] = Query(...),
    target_role: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get learning path for career progression."""
    service = AIService(db)
    return await service.generate_learning_path(current_skills, target_role)



