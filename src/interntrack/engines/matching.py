"""
Matching engine for skill-based job matching and recommendations.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.models import Skill, JobSkill, UserSkill
from interntrack.repositories.skill_repository import SkillRepository


class MatchingEngine:
    """Engine for matching user skills with job requirements."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_repo = SkillRepository(session)

    async def match_job_to_user(
        self,
        job_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Match a job's skill requirements against a user's skills."""
        from sqlalchemy import select
        from interntrack.domain.models import JobSkill, UserSkill

        # Get job skills
        job_skills_query = (
            select(JobSkill, Skill)
            .join(Skill, JobSkill.skill_id == Skill.id)
            .where(JobSkill.job_id == job_id)
        )
        job_skills_result = await self.session.execute(job_skills_query)
        job_skills = [
            {
                "skill_id": js.skill_id,
                "name": skill.name,
                "category": skill.category.value,
                "importance": js.importance,
            }
            for js, skill in job_skills_result.all()
        ]

        # Get user skills
        user_skills_query = (
            select(UserSkill, Skill)
            .join(Skill, UserSkill.skill_id == Skill.id)
            .where(UserSkill.user_id == user_id)
        )
        user_skills_result = await self.session.execute(user_skills_query)
        user_skills = {
            skill.name.lower(): {
                "skill_id": us.skill_id,
                "proficiency": us.proficiency_level,
            }
            for us, skill in user_skills_result.all()
        }

        # Calculate match
        matched = []
        missing = []
        partial = []

        for job_skill in job_skills:
            skill_name = job_skill["name"].lower()
            importance = job_skill["importance"]

            if skill_name in user_skills:
                proficiency = user_skills[skill_name]["proficiency"]
                # Consider it a full match if proficiency >= importance
                if proficiency >= importance:
                    matched.append({
                        "name": job_skill["name"],
                        "category": job_skill["category"],
                        "importance": importance,
                        "proficiency": proficiency,
                        "match_type": "full",
                    })
                else:
                    partial.append({
                        "name": job_skill["name"],
                        "category": job_skill["category"],
                        "importance": importance,
                        "proficiency": proficiency,
                        "gap": importance - proficiency,
                        "match_type": "partial",
                    })
            else:
                missing.append({
                    "name": job_skill["name"],
                    "category": job_skill["category"],
                    "importance": importance,
                    "match_type": "missing",
                })

        # Calculate match percentage
        total_importance = sum(js["importance"] for js in job_skills) or 1
        matched_importance = sum(m["importance"] for m in matched)
        partial_importance = sum(p["importance"] * 0.5 for p in partial)
        
        match_percentage = round(
            (matched_importance + partial_importance) / total_importance * 100,
            2
        )

        # Get recommendations for missing skills
        recommendations = await self._get_recommendations(missing)

        return {
            "job_id": job_id,
            "match_percentage": match_percentage,
            "matched_skills": matched,
            "partial_skills": partial,
            "missing_skills": missing,
            "recommendations": recommendations,
            "readiness_level": self._get_readiness_level(match_percentage),
        }

    async def find_matching_jobs(
        self,
        user_id: str,
        limit: int = 20,
        min_match: float = 50.0,
    ) -> List[Dict[str, Any]]:
        """Find jobs that match the user's skills."""
        from sqlalchemy import select
        from interntrack.domain.models import Job, JobSkill, UserSkill, Skill

        # Get user skills
        user_skills_query = (
            select(Skill.name)
            .join(UserSkill, UserSkill.skill_id == Skill.id)
            .where(UserSkill.user_id == user_id)
        )
        user_skills_result = await self.session.execute(user_skills_query)
        user_skill_names = {row[0].lower() for row in user_skills_result.all()}

        if not user_skill_names:
            return []

        # Get all active jobs with their skills
        jobs_query = (
            select(Job)
            .where(Job.is_active == True)
            .limit(100)  # Limit for performance
        )
        jobs_result = await self.session.execute(jobs_query)
        jobs = list(jobs_result.scalars().all())

        matching_jobs = []

        for job in jobs:
            # Get job skills
            job_skills_query = (
                select(JobSkill, Skill)
                .join(Skill, JobSkill.skill_id == Skill.id)
                .where(JobSkill.job_id == job.id)
            )
            job_skills_result = await self.session.execute(job_skills_query)
            job_skills = [(js, skill) for js, skill in job_skills_result.all()]

            if not job_skills:
                continue

            # Calculate match
            matched_count = sum(
                1 for _, skill in job_skills
                if skill.name.lower() in user_skill_names
            )
            match_percentage = (matched_count / len(job_skills)) * 100

            if match_percentage >= min_match:
                matching_jobs.append({
                    "job": {
                        "id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "url": job.url,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                    },
                    "match_percentage": round(match_percentage, 2),
                    "matched_skills": matched_count,
                    "total_skills": len(job_skills),
                })

        # Sort by match percentage
        matching_jobs.sort(key=lambda x: x["match_percentage"], reverse=True)

        return matching_jobs[:limit]

    async def get_skill_gap_analysis(
        self,
        user_id: str,
        target_role: str,
    ) -> Dict[str, Any]:
        """Analyze skill gaps for a target role."""
        from sqlalchemy import select
        from interntrack.domain.models import UserSkill, Skill

        # Get user skills
        user_skills_query = (
            select(Skill.name, Skill.category)
            .join(UserSkill, UserSkill.skill_id == Skill.id)
            .where(UserSkill.user_id == user_id)
        )
        user_skills_result = await self.session.execute(user_skills_query)
        user_skills = {row[0].lower(): row[1].value for row in user_skills_result.all()}

        # Get skills commonly required for the target role
        target_skills = await self._get_skills_for_role(target_role)

        matched = []
        missing = []

        for skill_name, category in target_skills.items():
            if skill_name.lower() in user_skills:
                matched.append({
                    "name": skill_name,
                    "category": category,
                })
            else:
                missing.append({
                    "name": skill_name,
                    "category": category,
                    "priority": self._get_skill_priority(skill_name, category),
                })

        # Sort missing by priority
        missing.sort(key=lambda x: x["priority"], reverse=True)

        match_percentage = (
            (len(matched) / len(target_skills) * 100)
            if target_skills
            else 0
        )

        return {
            "target_role": target_role,
            "match_percentage": round(match_percentage, 2),
            "matched_skills": matched,
            "missing_skills": missing,
            "total_required": len(target_skills),
            "total_matched": len(matched),
            "readiness_level": self._get_readiness_level(match_percentage),
        }

    async def _get_recommendations(
        self,
        missing_skills: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Get learning recommendations for missing skills."""
        recommendations = []

        for skill_info in missing_skills[:5]:  # Top 5 missing
            skill_name = skill_info["name"]
            skill = await self.skill_repo.get_by_name(skill_name)

            if skill and skill.learning_resources:
                recommendations.append({
                    "skill": skill_name,
                    "category": skill_info["category"],
                    "importance": skill_info["importance"],
                    "resources": skill.learning_resources[:3],
                })
            else:
                recommendations.append({
                    "skill": skill_name,
                    "category": skill_info["category"],
                    "importance": skill_info["importance"],
                    "resources": self._get_default_resources(skill_name),
                })

        return recommendations

    async def _get_skills_for_role(self, role: str) -> Dict[str, str]:
        """Get commonly required skills for a role."""
        # Default skill sets for common roles
        role_skills = {
            "backend developer": {
                "python": "programming",
                "javascript": "programming",
                "sql": "tool",
                "rest api": "framework",
                "git": "tool",
                "docker": "tool",
                "postgresql": "tool",
                "redis": "tool",
            },
            "frontend developer": {
                "javascript": "programming",
                "react": "framework",
                "html": "programming",
                "css": "programming",
                "typescript": "programming",
                "git": "tool",
                "rest api": "framework",
            },
            "full stack developer": {
                "python": "programming",
                "javascript": "programming",
                "react": "framework",
                "sql": "tool",
                "html": "programming",
                "css": "programming",
                "git": "tool",
                "docker": "tool",
                "rest api": "framework",
            },
            "data scientist": {
                "python": "programming",
                "sql": "tool",
                "machine learning": "tool",
                "pandas": "tool",
                "numpy": "tool",
                "tensorflow": "framework",
                "statistics": "soft_skill",
            },
            "devops engineer": {
                "python": "programming",
                "docker": "tool",
                "kubernetes": "tool",
                "aws": "tool",
                "terraform": "tool",
                "linux": "tool",
                "ci/cd": "tool",
                "git": "tool",
            },
            "mobile developer": {
                "javascript": "programming",
                "react native": "framework",
                "swift": "programming",
                "kotlin": "programming",
                "git": "tool",
                "rest api": "framework",
            },
        }

        # Try to find matching role
        role_lower = role.lower()
        for key, skills in role_skills.items():
            if key in role_lower or role_lower in key:
                return skills

        # Default skills
        return {
            "python": "programming",
            "javascript": "programming",
            "git": "tool",
            "sql": "tool",
            "rest api": "framework",
        }

    def _get_skill_priority(self, skill_name: str, category: str) -> int:
        """Get priority for a skill (higher = more important)."""
        high_priority = ["python", "javascript", "sql", "git", "rest api"]
        medium_priority = ["docker", "react", "aws", "kubernetes"]

        skill_lower = skill_name.lower()

        if skill_lower in high_priority:
            return 3
        elif skill_lower in medium_priority:
            return 2
        elif category == "programming":
            return 2
        else:
            return 1

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

    def _get_default_resources(self, skill_name: str) -> List[Dict[str, str]]:
        """Get default learning resources for a skill."""
        resources = {
            "python": [
                {"name": "Python.org Tutorial", "url": "https://docs.python.org/3/tutorial/"},
                {"name": "Real Python", "url": "https://realpython.com/"},
            ],
            "javascript": [
                {"name": "MDN Web Docs", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript"},
                {"name": "JavaScript.info", "url": "https://javascript.info/"},
            ],
            "react": [
                {"name": "React Documentation", "url": "https://react.dev/"},
                {"name": "React Tutorial", "url": "https://react.dev/learn"},
            ],
            "docker": [
                {"name": "Docker Documentation", "url": "https://docs.docker.com/"},
                {"name": "Docker Getting Started", "url": "https://docs.docker.com/get-started/"},
            ],
            "sql": [
                {"name": "SQLBolt", "url": "https://sqlbolt.com/"},
                {"name": "W3Schools SQL", "url": "https://www.w3schools.com/sql/"},
            ],
        }

        skill_lower = skill_name.lower()
        if skill_lower in resources:
            return resources[skill_lower]

        return [
            {"name": f"Search for {skill_name} tutorials", "url": f"https://www.google.com/search?q={skill_name}+tutorial"},
        ]
