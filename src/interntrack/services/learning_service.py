"""
Learning service for skill development recommendations.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import SkillCategory
from interntrack.domain.models import LearningPath, Skill
from interntrack.repositories.skill_repository import SkillRepository
from interntrack.services.ai_service import AIService


class LearningService:
    """Learning service for skill development."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_repo = SkillRepository(session)
        self.ai_service = AIService(session)

    async def get_learning_paths(
        self, skill_id: Optional[str] = None
    ) -> List[LearningPath]:
        """Get learning paths."""
        from sqlalchemy import select

        query = select(LearningPath)
        if skill_id:
            query = query.where(LearningPath.skill_id == skill_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_learning_path(self, data: dict) -> LearningPath:
        """Create a new learning path."""
        path = LearningPath(**data)
        self.session.add(path)
        await self.session.flush()
        return path

    async def get_recommendations(
        self, user_skills: List[str], target_role: str
    ) -> Dict[str, Any]:
        """Get personalized learning recommendations."""
        # Get missing skills for target role
        ai_result = await self.ai_service.generate_learning_path(
            user_skills, target_role
        )

        # Get available learning resources
        recommendations = []
        for skill_name in ai_result.get("skills", []):
            skill = await self.skill_repo.get_by_name(skill_name)
            if skill:
                recommendations.append({
                    "skill": skill.name,
                    "category": skill.category.value,
                    "resources": skill.learning_resources or [],
                })

        return {
            "target_role": target_role,
            "current_skills": user_skills,
            "missing_skills": ai_result.get("skills", []),
            "recommendations": recommendations,
            "learning_path": ai_result.get("steps", []),
        }

    async def get_platform_resources(self, platform: str) -> List[dict]:
        """Get resources from a specific learning platform."""
        from sqlalchemy import select

        query = select(LearningPath).where(LearningPath.platform == platform)
        result = await self.session.execute(query)
        paths = list(result.scalars().all())

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "estimated_hours": p.estimated_hours,
                "difficulty_level": p.difficulty_level,
            }
            for p in paths
        ]

    async def get_skill_gap_analysis(
        self, user_skills: List[str], job_skills: List[str]
    ) -> Dict[str, Any]:
        """Analyze skill gaps between user and job requirements."""
        user_set = set(s.lower() for s in user_skills)
        job_set = set(s.lower() for s in job_skills)

        matched = user_set & job_set
        missing = job_set - user_set
        extra = user_set - job_set

        match_percentage = (len(matched) / len(job_set) * 100) if job_set else 0

        return {
            "matched_skills": list(matched),
            "missing_skills": list(missing),
            "extra_skills": list(extra),
            "match_percentage": round(match_percentage, 2),
            "readiness_level": self._get_readiness_level(match_percentage),
        }

    def _get_readiness_level(self, percentage: float) -> str:
        """Get readiness level based on match percentage."""
        if percentage >= 80:
            return "excellent"
        elif percentage >= 60:
            return "good"
        elif percentage >= 40:
            return "moderate"
        else:
            return "needs_improvement"
