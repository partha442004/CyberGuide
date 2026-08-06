"""
Job Recommendation Engine

Recommends jobs based on:
1. Resume skills and proficiency levels
2. Job requirements and preferences
3. Location preferences
4. Experience level matching
5. Salary expectations
6. Company preferences
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.models import Job, UserSkill, Skill
from interntrack.repositories.job_repository import JobRepository

logger = logging.getLogger(__name__)


class JobRecommender:
    """AI-powered job recommendation engine."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
    
    async def get_personalized_recommendations(
        self,
        user_id: str,
        limit: int = 20,
        location_filter: str | None = None,
        min_match_score: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Get personalized job recommendations for a user."""
        
        # 1. Get user's skills and preferences
        user_profile = await self._build_user_profile(user_id)
        
        if not user_profile["skills"]:
            return []
        
        # 2. Get all active jobs
        jobs = await self.job_repo.get_recent_jobs(days=30)
        
        # 3. Score and rank jobs
        recommendations = []
        for job in jobs:
            score = self._calculate_job_score(job, user_profile, location_filter)
            if score >= min_match_score:
                recommendations.append({
                    "job": {
                        "id": str(job.id),
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "url": job.url,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                        "tags": list(job.tags or []),
                    },
                    "match_score": round(score, 1),
                    "match_reasons": self._get_match_reasons(job, user_profile),
                    "skill_gaps": self._identify_skill_gaps(job, user_profile),
                })
        
        # 4. Sort by score and return top results
        recommendations.sort(key=lambda x: x["match_score"], reverse=True)
        
        return recommendations[:limit]
    
    async def _build_user_profile(self, user_id: str) -> dict[str, Any]:
        """Build comprehensive user profile from skills and preferences."""
        
        # Get user skills
        query = (
            select(UserSkill, Skill)
            .join(Skill, UserSkill.skill_id == Skill.id)
            .where(UserSkill.user_id == user_id)
        )
        result = await self.session.execute(query)
        
        skills = {}
        categories = set()
        
        for user_skill, skill in result.all():
            skills[skill.name.lower()] = {
                "proficiency": user_skill.proficiency_level,
                "category": skill.category.value if hasattr(skill.category, 'value') else str(skill.category),
            }
            categories.add(skill.category.value if hasattr(skill.category, 'value') else str(skill.category))
        
        # Get user preferences (if available)
        preferences = await self._get_user_preferences(user_id)
        
        return {
            "user_id": user_id,
            "skills": skills,
            "categories": list(categories),
            "preferences": preferences,
        }
    
    async def _get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """Get user's job preferences."""
        try:
            from interntrack.domain.models import User
            
            query = select(User).where(User.id == user_id)
            result = await self.session.execute(query)
            user = result.scalar_one_or_none()
            
            if user:
                return {
                    "location": getattr(user, "location", None),
                    "preferred_roles": getattr(user, "preferred_roles", []),
                    "salary_min": getattr(user, "salary_min", None),
                    "salary_max": getattr(user, "salary_max", None),
                    "remote_only": getattr(user, "remote_only", False),
                }
        except Exception:
            pass
        
        return {}
    
    def _calculate_job_score(
        self,
        job: Any,
        user_profile: dict,
        location_filter: str | None,
    ) -> float:
        """Calculate match score between job and user profile."""
        
        score = 0.0
        weights = {
            "skill_match": 0.4,
            "category_match": 0.2,
            "location_match": 0.15,
            "experience_match": 0.15,
            "recency": 0.1,
        }
        
        # 1. Skill match score
        job_skills = self._extract_job_skills(job)
        user_skills = user_profile["skills"]
        
        if job_skills:
            matched = 0
            for skill in job_skills:
                skill_lower = skill.lower()
                if skill_lower in user_skills:
                    proficiency = user_skills[skill_lower]["proficiency"]
                    matched += proficiency / 5.0  # Normalize to 0-1
            
            skill_score = (matched / len(job_skills)) * 100 if job_skills else 0
            score += skill_score * weights["skill_match"]
        
        # 2. Category match score
        job_categories = self._extract_job_categories(job)
        user_categories = set(user_profile["categories"])
        
        if job_categories:
            category_overlap = len(set(job_categories) & user_categories)
            category_score = (category_overlap / len(job_categories)) * 100
            score += category_score * weights["category_match"]
        
        # 3. Location match score
        location_score = self._calculate_location_score(job, user_profile, location_filter)
        score += location_score * weights["location_match"]
        
        # 4. Experience level match
        experience_score = self._calculate_experience_match(job, user_profile)
        score += experience_score * weights["experience_match"]
        
        # 5. Recency score (newer jobs get higher score)
        recency_score = self._calculate_recency_score(job)
        score += recency_score * weights["recency"]
        
        return min(score, 100.0)
    
    def _extract_job_skills(self, job: Any) -> list[str]:
        """Extract skills from job data."""
        skills = []
        
        # From tags
        if hasattr(job, 'tags') and job.tags:
            skills.extend([t.lower() for t in job.tags if isinstance(t, str)])
        
        # From title
        if hasattr(job, 'title') and job.title:
            title_lower = job.title.lower()
            # Extract common skills from title
            skill_keywords = [
                "python", "javascript", "java", "react", "node", "aws", "docker",
                "kubernetes", "security", "cyber", "soc", "pentest", "vapt",
                "sql", "nosql", "redis", "postgresql", "mongodb",
            ]
            for skill in skill_keywords:
                if skill in title_lower and skill not in skills:
                    skills.append(skill)
        
        # From description (if available)
        if hasattr(job, 'description') and job.description:
            desc_lower = job.description.lower()
            skill_keywords = [
                "python", "javascript", "java", "react", "node", "aws", "docker",
                "kubernetes", "security", "cyber", "soc", "pentest", "vapt",
                "sql", "nosql", "redis", "postgresql", "mongodb",
            ]
            for skill in skill_keywords:
                if skill in desc_lower and skill not in skills:
                    skills.append(skill)
        
        return list(set(skills))
    
    def _extract_job_categories(self, job: Any) -> list[str]:
        """Extract categories from job data."""
        categories = []
        
        title_lower = (getattr(job, 'title', '') or '').lower()
        tags = getattr(job, 'tags', []) or []
        tags_lower = [t.lower() for t in tags if isinstance(t, str)]
        
        # Map to categories
        category_keywords = {
            "security": ["security", "cyber", "soc", "pentest", "vapt", "infosec", "appsec"],
            "programming": ["developer", "engineer", "programmer", "software"],
            "data": ["data", "analyst", "analytics", "scientist"],
            "devops": ["devops", "sre", "infrastructure", "cloud"],
            "design": ["design", "ux", "ui", "graphic"],
        }
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in title_lower or keyword in tags_lower:
                    if category not in categories:
                        categories.append(category)
                    break
        
        return categories
    
    def _calculate_location_score(
        self,
        job: Any,
        user_profile: dict,
        location_filter: str | None,
    ) -> float:
        """Calculate location match score."""
        job_location = (getattr(job, 'location', '') or '').lower()
        user_location = user_profile.get("preferences", {}).get("location", "")
        remote_only = user_profile.get("preferences", {}).get("remote_only", False)
        
        # Check for remote work
        if remote_only and ("remote" in job_location or "anywhere" in job_location):
            return 100.0
        
        # Check location filter
        if location_filter:
            if location_filter.lower() in job_location:
                return 100.0
            elif "remote" in job_location:
                return 80.0
            else:
                return 30.0
        
        # Check user location
        if user_location:
            if user_location.lower() in job_location:
                return 100.0
            elif "remote" in job_location:
                return 80.0
            else:
                return 50.0
        
        # Default score for unknown location
        return 60.0
    
    def _calculate_experience_match(self, job: Any, user_profile: dict) -> float:
        """Calculate experience level match."""
        title_lower = (getattr(job, 'title', '') or '').lower()
        
        # Extract job experience level
        job_level = "mid"  # Default
        if any(kw in title_lower for kw in ["senior", "lead", "principal", "staff", "architect"]):
            job_level = "senior"
        elif any(kw in title_lower for kw in ["junior", "entry", "associate", "fresher", "intern"]):
            job_level = "junior"
        
        # Estimate user experience level from skills
        user_skills = user_profile.get("skills", {})
        avg_proficiency = sum(s["proficiency"] for s in user_skills.values()) / len(user_skills) if user_skills else 3
        
        if avg_proficiency >= 4:
            user_level = "senior"
        elif avg_proficiency >= 2.5:
            user_level = "mid"
        else:
            user_level = "junior"
        
        # Match levels
        level_match = {
            ("senior", "senior"): 100,
            ("senior", "mid"): 70,
            ("senior", "junior"): 40,
            ("mid", "senior"): 60,
            ("mid", "mid"): 100,
            ("mid", "junior"): 80,
            ("junior", "senior"): 30,
            ("junior", "mid"): 70,
            ("junior", "junior"): 100,
        }
        
        return level_match.get((user_level, job_level), 50)
    
    def _calculate_recency_score(self, job: Any) -> float:
        """Calculate recency score (newer jobs get higher score)."""
        posted_at = getattr(job, 'posted_at', None)
        if not posted_at:
            return 50.0
        
        if isinstance(posted_at, datetime):
            days_ago = (datetime.now(timezone.utc) - posted_at).days
        else:
            return 50.0
        
        # Score decreases with age
        if days_ago <= 1:
            return 100.0
        elif days_ago <= 3:
            return 80.0
        elif days_ago <= 7:
            return 60.0
        elif days_ago <= 14:
            return 40.0
        else:
            return 20.0
    
    def _get_match_reasons(self, job: Any, user_profile: dict) -> list[str]:
        """Generate human-readable match reasons."""
        reasons = []
        
        job_skills = self._extract_job_skills(job)
        user_skills = user_profile["skills"]
        
        matched_skills = [s for s in job_skills if s.lower() in user_skills]
        if matched_skills:
            reasons.append(f"Your skills match: {', '.join(matched_skills[:3])}")
        
        job_categories = self._extract_job_categories(job)
        user_categories = set(user_profile["categories"])
        common_categories = set(job_categories) & user_categories
        if common_categories:
            reasons.append(f"Matches your expertise: {', '.join(common_categories)}")
        
        job_location = (getattr(job, 'location', '') or '').lower()
        if "remote" in job_location:
            reasons.append("Remote work available")
        
        return reasons[:5]
    
    def _identify_skill_gaps(self, job: Any, user_profile: dict) -> list[str]:
        """Identify skills the user is missing for this job."""
        job_skills = self._extract_job_skills(job)
        user_skills = user_profile["skills"]
        
        gaps = []
        for skill in job_skills:
            if skill.lower() not in user_skills:
                gaps.append(skill)
        
        return gaps[:5]


async def get_job_recommendations(
    session: AsyncSession,
    user_id: str,
    limit: int = 20,
    location_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Main function to get job recommendations."""
    recommender = JobRecommender(session)
    return await recommender.get_personalized_recommendations(
        user_id=user_id,
        limit=limit,
        location_filter=location_filter,
    )
