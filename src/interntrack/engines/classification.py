"""
Classification engine for job categorization.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import ExperienceLevel, JobType, SkillCategory
from interntrack.domain.models import Skill
from interntrack.repositories.skill_repository import SkillRepository
from interntrack.services.ai_service import AIService


class ClassificationEngine:
    """Engine for classifying and categorizing jobs."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_repo = SkillRepository(session)
        self.ai_service = AIService(session)

    async def classify_job(self, job_data: dict) -> Dict[str, Any]:
        """Classify a job posting."""
        # Try AI classification first
        classification = await self.ai_service.classify_job(job_data)

        # Fall back to rule-based if AI fails
        if "error" in classification:
            classification = self._rule_based_classify(job_data)

        # Extract and match skills
        skills = await self._extract_skills(
            classification.get("skills", []),
            job_data.get("description", ""),
        )

        return {
            **classification,
            "matched_skills": skills,
        }

    async def _extract_skills(
        self, ai_skills: List[str], description: str
    ) -> List[Dict[str, Any]]:
        """Extract and categorize skills from job."""
        skills = []

        # Process AI-detected skills
        for skill_name in ai_skills:
            skill = await self.skill_repo.create_or_get(
                skill_name.lower(),
                self._categorize_skill(skill_name),
            )
            skills.append({
                "id": skill.id,
                "name": skill.name,
                "category": skill.category.value,
            })

        # Also extract from description using patterns
        pattern_skills = self._extract_skills_from_text(description)
        for skill_name in pattern_skills:
            if not any(s["name"] == skill_name.lower() for s in skills):
                skill = await self.skill_repo.create_or_get(
                    skill_name.lower(),
                    self._categorize_skill(skill_name),
                )
                skills.append({
                    "id": skill.id,
                    "name": skill.name,
                    "category": skill.category.value,
                })

        return skills

    def _categorize_skill(self, skill_name: str) -> SkillCategory:
        """Categorize a skill by name."""
        skill_lower = skill_name.lower()

        programming = [
            "python", "javascript", "typescript", "java", "c++", "go", "rust",
            "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
        ]

        frameworks = [
            "react", "vue", "angular", "django", "flask", "fastapi", "express",
            "spring", "rails", "laravel", "nextjs", "nuxt", "svelte",
        ]

        tools = [
            "docker", "kubernetes", "aws", "gcp", "azure", "git", "linux",
            "jenkins", "terraform", "ansible", "redis", "postgresql", "mysql",
        ]

        if skill_lower in programming:
            return SkillCategory.PROGRAMMING
        elif skill_lower in frameworks:
            return SkillCategory.FRAMEWORK
        elif skill_lower in tools:
            return SkillCategory.TOOL
        else:
            return SkillCategory.SOFT_SKILL

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skills from text using pattern matching."""
        import re

        known_skills = [
            "python", "javascript", "typescript", "react", "vue", "angular",
            "node.js", "django", "flask", "fastapi", "postgresql", "mysql",
            "redis", "docker", "kubernetes", "aws", "gcp", "azure", "git",
            "linux", "sql", "html", "css", "rest", "graphql", "ci/cd",
        ]

        found_skills = []
        text_lower = text.lower()

        for skill in known_skills:
            if skill in text_lower:
                found_skills.append(skill)

        return list(set(found_skills))

    def _rule_based_classify(self, job_data: dict) -> Dict[str, Any]:
        """Rule-based classification fallback."""
        title = job_data.get("title", "").lower()
        description = job_data.get("description", "").lower()

        # Determine job type
        job_type = JobType.UNKNOWN
        if "intern" in title:
            job_type = JobType.INTERNSHIP
        elif "remote" in title or "remote" in description:
            job_type = JobType.REMOTE
        elif "contract" in title or "freelance" in title:
            job_type = JobType.CONTRACT

        # Determine experience level
        experience = ExperienceLevel.UNKNOWN
        if any(w in title for w in ["senior", "lead", "principal"]):
            experience = ExperienceLevel.SENIOR
        elif any(w in title for w in ["junior", "entry", "associate"]):
            experience = ExperienceLevel.JUNIOR
        elif "mid" in title or "intermediate" in title:
            experience = ExperienceLevel.MID

        return {
            "job_type": job_type.value,
            "experience_level": experience.value,
            "skills": self._extract_skills_from_text(description),
            "is_remote": "remote" in title or "remote" in description,
            "confidence": 0.6,
        }

    async def get_skill_demand(self) -> List[Dict[str, Any]]:
        """Get skill demand statistics from job listings."""
        from interntrack.domain.models import JobSkill, Job
        from sqlalchemy import func, select

        query = (
            select(
                Skill.name,
                Skill.category,
                func.count(JobSkill.job_id).label("demand")
            )
            .join(JobSkill, Skill.id == JobSkill.skill_id)
            .join(Job, JobSkill.job_id == Job.id)
            .where(Job.is_active == True)
            .group_by(Skill.id)
            .order_by(func.count(JobSkill.job_id).desc())
            .limit(20)
        )

        result = await self.session.execute(query)
        return [
            {
                "skill": row.name,
                "category": row.category.value,
                "demand": row.demand,
            }
            for row in result.all()
        ]
