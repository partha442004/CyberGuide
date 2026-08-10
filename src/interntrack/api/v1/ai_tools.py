"""
AI job-hunting tools — cover letter, interview questions, why-I-match.

Each tool combines the user's resume skills with the job's title /
company / description. When Gemini is configured it writes the copy;
otherwise a solid template generator steps in, so the feature works even
without an AI key. All endpoints are read-only and never raise on AI
failure (they degrade to templates).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.services.job_service import JobService

router = APIRouter()


def _template_cover_letter(
    title: str,
    company: str,
    matched: list[str],
    missing: list[str],
) -> str:
    """A solid, tailored cover letter without an AI backend."""
    company_name = company or "your team"
    skill_line = ", ".join(matched[:6]) if matched else "the skills this role needs"
    growth = (
        f" I am actively closing the gap in {', '.join(missing[:3])}."
        if missing
        else ""
    )
    return (
        f"Subject: Application for {title} at {company_name}\n\n"
        f"Dear Hiring Team,\n\n"
        f"I am applying for the {title} role at {company_name}. "
        f"My background maps directly onto what the position calls for: "
        f"{skill_line}.{growth}\n\n"
        f"In my recent work I have delivered hands-on results and stayed "
        f"current with the tools and practices the role relies on. I would "
        f"be glad to walk you through concrete examples in an interview, "
        f"and to show how I can start contributing from week one.\n\n"
        f"Thank you for your time and consideration.\n\n"
        f"Best regards,\n[Your Name]"
    )


def _template_questions(title: str, company: str, skills: list[str]) -> list[str]:
    """Five interview questions shaped by the role and its skills."""
    skill = ", ".join(skills[:4]) if skills else "the core requirements"
    return [
        f"Walk me through your most relevant experience for {title}.",
        f"How have you applied {skill} in a real project or engagement?",
        f"What does a typical day look like for a strong {title}?",
        (
            f"Tell me about a difficult problem at a company like {company} "
            f"you solved and how you approached it."
        ),
        f"What would you want to learn or improve in your first 90 days in {title}?",
    ]


async def _gemini_text(prompt: str) -> str | None:
    """One-shot Gemini text completion; None when unavailable/failed."""
    try:
        from interntrack.config import get_settings

        settings = get_settings()
        if not settings.gemini_api_key:
            return None
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(prompt)
        return str(response.text)
    except Exception:
        return None


def _why_match_lines(matched: list[str], missing: list[str]) -> list[str]:
    lines = []
    if matched:
        lines.append("Your resume directly covers: " + ", ".join(matched[:8]) + ".")
    else:
        lines.append("No explicit skill overlap found in your resume yet.")
    if missing:
        lines.append(
            "Consider highlighting or building: " + ", ".join(missing[:6]) + "."
        )
    return lines


@router.post("/jobs/{job_id}/apply-kit")
async def apply_kit(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cover letter + interview questions + why-I-match for one job."""
    service = JobService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    title = str(job.title or "")
    company = str(job.company or "Unknown")
    description = str(job.description or "")

    from interntrack.scheduler.jobs import (
        _job_match_score,
        _latest_resume_skill_names,
    )

    resume_skills = await _latest_resume_skill_names(db) or set()
    required = [str(s) for s in (getattr(job, "required_skills", None) or [])]
    tags = [str(t) for t in (getattr(job, "tags", None) or [])]
    # Soft match against every signal we have.
    haystack = " ".join([title, company] + required + tags).lower()
    matched = sorted(s for s in resume_skills if str(s).lower() in haystack)
    missing = [
        s for s in required if str(s).lower() not in {m.lower() for m in matched}
    ]

    score = _job_match_score(resume_skills, {"required_skills": required, "tags": tags})

    # Gemini polish (optional) — templates otherwise.
    cover_letter = _template_cover_letter(title, company, matched, missing)
    questions = _template_questions(title, company, matched or required)
    prompt = (
        f"Write a concise, professional cover letter (max 180 words) for the "
        f"{title} role at {company}. The candidate's skills: "
        f"{', '.join(matched) or 'none listed'}. Job description: "
        f"{description[:900]}"
    )
    ai_letter = await _gemini_text(prompt)
    if ai_letter:
        cover_letter = ai_letter.strip()

    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "match_score": round(float(score), 1) if score is not None else None,
        "why_match": _why_match_lines(matched, missing),
        "matched_skills": matched[:12],
        "missing_skills": missing[:12],
        "cover_letter": cover_letter,
        "interview_questions": questions,
        "generated_by": "gemini" if ai_letter else "template",
    }
