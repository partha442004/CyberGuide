"""
AI service for job classification and skill matching.
"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.config import get_settings
from interntrack.domain.enums import ExperienceLevel, JobType
from interntrack.repositories.skill_repository import SkillRepository

settings = get_settings()


class AIService:
    """AI service for classification and recommendations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_repo = SkillRepository(session)

    async def classify_job(self, job_data: dict) -> dict[str, Any]:
        """Classify a job posting using AI."""
        prompt = self._build_classification_prompt(job_data)

        if settings.gemini_api_key:
            return await self._classify_with_gemini(prompt)
        if settings.ollama_base_url:
            return await self._classify_with_ollama(prompt)
        return self._classify_with_rules(job_data)

    def _build_classification_prompt(self, job_data: dict) -> str:
        """Build prompt for job classification."""
        return f"""Classify this job posting:

Title: {job_data.get("title", "N/A")}
Company: {job_data.get("company", "N/A")}
Description: {job_data.get("description", "N/A")[:500]}

Return JSON with:
- job_type: internship|full_time|part_time|contract|freelance|remote
- experience_level: entry|junior|mid|senior|lead|executive
- skills: list of required skills
- is_remote: boolean
- confidence: 0.0-1.0
"""

    async def _classify_with_gemini(self, prompt: str) -> dict[str, Any]:
        """Classify using Google Gemini API."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model)
            response = model.generate_content(prompt)
            return json.loads(response.text)
        except Exception:
            return {"error": "Gemini classification failed"}

    async def _classify_with_ollama(self, prompt: str) -> dict[str, Any]:
        """Classify using local Ollama."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "format": "json",
                    },
                    timeout=60,
                )
                if response.status_code == 200:
                    return json.loads(response.json().get("response", "{}"))
        except Exception:
            pass
        return {"error": "Ollama classification failed"}

    def _classify_with_rules(self, job_data: dict) -> dict[str, Any]:
        """Rule-based classification fallback."""
        title = job_data.get("title", "").lower()
        description = job_data.get("description", "").lower()

        job_type = JobType.UNKNOWN
        if "intern" in title:
            job_type = JobType.INTERNSHIP
        elif "remote" in title:
            job_type = JobType.REMOTE

        experience = ExperienceLevel.UNKNOWN
        if "senior" in title or "lead" in title:
            experience = ExperienceLevel.SENIOR
        elif "junior" in title or "entry" in title:
            experience = ExperienceLevel.JUNIOR

        return {
            "job_type": job_type.value,
            "experience_level": experience.value,
            "skills": [],
            "is_remote": "remote" in title.lower() or "remote" in description.lower(),
            "confidence": 0.5,
        }

    async def match_skills(
        self,
        job_skills: list[str],
        user_skills: list[str],
    ) -> dict[str, Any]:
        """Match job skills with user skills."""
        matched = set(job_skills) & set(user_skills)
        missing = set(job_skills) - set(user_skills)

        match_percentage = len(matched) / len(job_skills) * 100 if job_skills else 0

        return {
            "matched_skills": list(matched),
            "missing_skills": list(missing),
            "match_percentage": round(match_percentage, 2),
            "recommendations": await self._get_skill_recommendations(list(missing)),
        }

    async def _get_skill_recommendations(self, skills: list[str]) -> list[dict]:
        """Get learning recommendations for missing skills."""
        recommendations = []
        for skill_name in skills:
            skill = await self.skill_repo.get_by_name(skill_name)
            if skill and skill.learning_resources:
                recommendations.append(
                    {
                        "skill": skill_name,
                        "category": skill.category.value,
                        "resources": skill.learning_resources[:3],
                    }
                )
        return recommendations

    async def generate_learning_path(
        self,
        current_skills: list[str],
        target_role: str,
    ) -> dict[str, Any]:
        """Generate a learning path for career progression."""
        skills_str = ", ".join(current_skills)
        prompt = (
            f"Create a learning path for someone with skills: {skills_str}\n"
            f"Target role: {target_role}\n"
            f"Include courses from: Google Cloud Skills Boost, OWASP, "
            f"PortSwigger, TryHackMe, Hack The Box, OverTheWire, PicoCTF\n"
            f"Return JSON with steps, estimated time, and resources."
        )

        try:
            if settings.gemini_api_key:
                return await self._classify_with_gemini(prompt)
            if settings.ollama_base_url:
                return await self._classify_with_ollama(prompt)
        except Exception:
            pass

        return {"steps": [], "message": "AI service not configured"}
