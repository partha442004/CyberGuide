"""
Resumes API Router

Endpoints for resume upload, parsing, matching, and skill extraction.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.dependencies import get_session
from cybershield.domain.models import Job, ResumeData, ResumeMatchResult
from cybershield.schemas.resume import (
    ResumeBatchMatchResponse,
    ResumeMatchResponse,
    ResumeUploadResponse,
)
from cybershield.services.resume_service import SECURITY_SKILLS, ResumeParser
from cybershield.utils import utcnow

router = APIRouter()

# Non-skill tokens that commonly appear in a job's ``tags`` column
# (e.g. ``remote``, ``hybrid``) — excluded from matching so they never
# pollute ``missing_skills`` or the "Learn missing skills" suggestion.
_NON_SKILL_TAGS = frozenset(
    {
        "remote",
        "hybrid",
        "onsite",
        "on-site",
        "full-time",
        "full time",
        "part-time",
        "part time",
        "contract",
        "internship",
        "entry level",
        "entry-level",
        "mid level",
        "senior level",
        "temporary",
        "permanent",
        "relocation",
        "visa sponsorship",
        "work from home",
    }
)

# ---------------------------------------------------------------------------
# Fair skill matching for domain-transition candidates
#
# Exact-name overlap alone scores a resume 0.0 against any job whose skill
# list uses different wording (e.g. a Data Analyst resume with ``python`` /
# ``sql`` vs a Software Engineer job asking for ``go`` / ``kubernetes``).
# To score domain-transition candidates more fairly we add two extra tiers
# of partial credit on top of exact matches:
#
#   1. SYNONYM matches — equivalent names for the same skill
#      (e.g. ``k8s`` == ``kubernetes``, ``golang`` == ``go``).
#   2. CATEGORY matches — skills in the same domain family
#      (e.g. ``python`` (scripting) partially covers a job asking for
#      ``go`` (scripting) because the transferable skill set overlaps).
#
# Tiers are weighted so exact matches still dominate the score:
#   required  : exact 1.0, synonym 0.6, category 0.35
#   preferred : exact 1.0, synonym 0.5, category 0.20
# ---------------------------------------------------------------------------

# Curated synonym groups: any name in a group matches any other name.
_SYNONYM_GROUPS = (
    {"k8s", "kubernetes"},
    {"golang", "go"},
    {"js", "javascript"},
    {"ts", "typescript"},
    {"node", "node.js"},
    {"aws", "amazon web services"},
    {"gcp", "google cloud"},
    {"ml", "machine learning"},
    {"ai", "artificial intelligence"},
    {"powerbi", "power bi"},
    {"ms excel", "excel", "microsoft excel"},
    {"git", "github"},
    {"reactjs", "react"},
    {"vuejs", "vue.js"},
    {"c", "c/c++"},
    # Domain-level words: a job tagged only with the generic "security"
    # (very common in scraper tag lists) must still match a resume that
    # lists "cybersecurity"/"infosec", instead of flatlining at 0.0.
    {"security", "cybersecurity", "infosec", "information security"},
    {"software engineering", "software engineer", "software developer"},
    {"data science", "data scientist", "data analyst"},
)

# Flatten synonym groups into a name -> frozenset(synonyms) lookup.
_SYNONYM_LOOKUP: dict = {}
for _group in _SYNONYM_GROUPS:
    _syns = frozenset(_group)
    for _name in _group:
        _SYNONYM_LOOKUP.setdefault(_name, set()).update(_syns)

# Category map reused from the resume parser's skill vocabulary, so resume
# skills and job skills are categorized consistently. Additional common
# job-side terms (not in the security-focused parser vocabulary) are mapped
# by hand so software/cloud/data roles get fair category credit too.
_SKILL_CATEGORY_MAP: dict = {}
for _category, _skills in SECURITY_SKILLS.items():
    for _skill in _skills:
        _SKILL_CATEGORY_MAP[_skill] = _category
# Extra job-side terms missing from the parser vocabulary.
_SKILL_CATEGORY_MAP.update(
    {
        "java": "scripting",
        "c++": "scripting",
        "c#": "scripting",
        "c": "scripting",
        "go": "scripting",
        "rust": "scripting",
        "kubernetes": "cicd_security",
        "docker": "cicd_security",
        "aws": "cloud_security",
        "azure": "cloud_security",
        "gcp": "cloud_security",
        "sql": "data_analysis",
        "python": "scripting",
        "git": "cicd_security",
    }
)

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024


@dataclass
class _JobMatchData:
    """Lightweight job payload for matching.

    We deliberately load only the columns matching needs — never the full
    ORM ``Job`` entity. The cybershield ``Job`` model declares eager
    relationships (``applications``, ``skills``, ...) that join against
    tables whose shapes differ in the live interntrack schema, crashing on
    the deployed app. A column-only select sidesteps that entirely.
    """

    id: str
    title: Optional[str]
    company: Optional[str]
    required_skills: Any
    preferred_skills: Any
    tags: Any


def _as_list(value: Any) -> list:
    """Normalize a JSON column value to a list."""
    return list(value or [])


def _serialize_resume_response(resume: ResumeData) -> ResumeUploadResponse:
    """Helper to serialize ResumeData to response model."""
    return ResumeUploadResponse(
        id=resume.id,
        user_id=resume.user_id,
        file_name=resume.file_path,
        file_hash=resume.file_hash,
        skills=[s for s in _as_list(resume.skills) if s],
        education=[e for e in _as_list(resume.education) if e],
        experience=[x for x in _as_list(resume.experience) if x],
        certifications=[c for c in _as_list(resume.certifications) if c],
        projects=[p for p in _as_list(resume.projects) if p],
        links={"github": resume.github_url or "", "linkedin": resume.linkedin_url or ""},
        parsed_at=resume.parsed_at,
    )


def _extract_skill_names(skills_list) -> set:
    """Extract lowercase skill names from a list of skills."""
    result = set()
    for s in skills_list or []:
        if isinstance(s, str) and s:
            result.add(s.lower())
        elif isinstance(s, dict):
            name = s.get("name", "")
            if name:
                result.add(name.lower())
    return result


def _synonym_hits(skill: str, resume_skills: set) -> set:
    """Return resume skills that are synonyms of ``skill`` (excluding itself)."""
    syns = _SYNONYM_LOOKUP.get(skill)
    if not syns:
        return set()
    return {s for s in syns if s != skill} & resume_skills


def _skill_category(skill: str) -> Optional[str]:
    """Map a lowercase skill name to its domain category."""
    return _SKILL_CATEGORY_MAP.get(skill)


def _calculate_job_match(resume_skills: set, job: _JobMatchData) -> ResumeMatchResponse:
    """Calculate match score between resume skills and a job.

    Scores in three tiers so domain-transition candidates are treated
    fairly instead of flatlining at 0.0:

    * **exact**   — the resume literally lists the job's skill (full credit)
    * **synonym** — the resume lists an equivalent name (partial credit)
    * **category**— the resume lists a same-family skill, e.g. ``python``
      covering ``go`` (both ``scripting``) — transferable-skill credit

    Falls back to the job's ``tags`` column (used by the interntrack Job
    model / live Neon table) when the dedicated skill columns are empty.
    """
    job_required = _extract_skill_names(getattr(job, "required_skills", None))
    job_preferred = _extract_skill_names(getattr(job, "preferred_skills", None))
    if not job_required and not job_preferred:
        # Live jobs (interntrack model) keep skills in ``tags`` — filter out
        # non-skill tokens (``remote``, ``full-time`` ...) so they never
        # appear as bogus missing skills.
        job_tags = _extract_skill_names(getattr(job, "tags", None)) - _NON_SKILL_TAGS
        job_required = job_tags
    all_job_skills = job_required | job_preferred

    matched: List[str] = []
    related: List[str] = []
    missing: List[str] = []

    if not all_job_skills:
        match_score = None
    else:
        # Resume categories are derived from the shared vocabulary so
        # ``python`` (scripting) can partially cover ``go`` (scripting).
        resume_categories = {cat for s in resume_skills if (cat := _skill_category(s)) is not None}

        def _tier(skill: str, is_preferred: bool = False) -> Tuple[float, str]:
            """Classify a job skill against the resume.

            Returns (earned_weight, bucket) where bucket is one of
            ``exact``/``synonym``/``category``/``none``. Weights differ for
            preferred skills so the documented table is honored exactly:

              required  : exact 1.0, synonym 0.6, category 0.35
              preferred : exact 1.0, synonym 0.5, category 0.20
            """
            if skill in resume_skills:
                return 1.0, "exact"
            if _synonym_hits(skill, resume_skills):
                return (0.5 if is_preferred else 0.6), "synonym"
            cat = _skill_category(skill)
            if cat is not None and cat in resume_categories:
                return (0.2 if is_preferred else 0.35), "category"
            return 0.0, "none"

        required_earned = 0.0
        preferred_earned = 0.0

        for skill in job_required:
            weight, tier = _tier(skill)
            required_earned += weight
            if tier in ("exact", "synonym"):
                matched.append(skill)
            elif tier == "category":
                related.append(skill)
            else:
                missing.append(skill)

        for skill in job_preferred:
            weight, tier = _tier(skill, is_preferred=True)
            preferred_earned += weight
            if tier in ("exact", "synonym"):
                matched.append(skill)
            elif tier == "category":
                related.append(skill)
            else:
                missing.append(skill)

        req_total = max(len(job_required), 1)
        pref_total = max(len(job_preferred), 1)
        match_score = round(
            (required_earned / req_total * 0.7 + preferred_earned / pref_total * 0.3) * 100,
            1,
        )

    suggestions = []
    if missing:
        suggestions.append(f"Learn missing skills: {', '.join(missing[:5])}")
    if related:
        suggestions.append(
            "Transferable skills: your resume covers "
            f"{', '.join(sorted(related)[:4])} from the same domains"
        )
    if match_score is not None:
        if match_score >= 80:
            suggestions.append("Strong match! Apply now")
        elif match_score >= 50:
            suggestions.append("Good match - consider applying")
        else:
            suggestions.append("Build projects with required skills")

    return ResumeMatchResponse(
        job_id=job.id,
        job_title=job.title,
        company=job.company,
        match_score=match_score,
        matched_skills=matched,
        related_skills=related,
        missing_skills=missing,
        suggestions=suggestions,
    )


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    user_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload and parse a resume PDF."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    parser = ResumeParser()
    try:
        parsed_data = await parser.parse_upload(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}") from e

    existing = await session.execute(select(ResumeData).where(ResumeData.user_id == user_id))
    existing_resume = existing.scalar_one_or_none()
    skills_data = parsed_data.get("skills", [])

    if existing_resume:
        existing_resume.file_path = file.filename  # type: ignore[assignment]
        existing_resume.file_hash = parsed_data["file_hash"]
        existing_resume.skills = skills_data
        existing_resume.education = parsed_data.get("education", [])
        existing_resume.experience = parsed_data.get("experience", [])
        existing_resume.projects = parsed_data.get("projects", [])
        existing_resume.certifications = parsed_data.get("certifications", [])
        existing_resume.github_url = parsed_data.get("links", {}).get("github")
        existing_resume.linkedin_url = parsed_data.get("links", {}).get("linkedin")
        existing_resume.parsed_at = utcnow()  # type: ignore[assignment]
        resume = existing_resume
    else:
        resume = ResumeData(
            user_id=user_id,
            file_path=file.filename,
            file_hash=parsed_data["file_hash"],
            skills=skills_data,
            education=parsed_data.get("education", []),
            experience=parsed_data.get("experience", []),
            projects=parsed_data.get("projects", []),
            certifications=parsed_data.get("certifications", []),
            github_url=parsed_data.get("links", {}).get("github"),
            linkedin_url=parsed_data.get("links", {}).get("linkedin"),
            parsed_at=utcnow(),
        )
        session.add(resume)

    await session.flush()
    return _serialize_resume_response(resume)


@router.get("/{user_id}", response_model=ResumeUploadResponse)
async def get_resume(user_id: str, session: AsyncSession = Depends(get_session)):
    """Get the user's parsed resume data."""
    result = await session.execute(select(ResumeData).where(ResumeData.user_id == user_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found for this user.")
    return _serialize_resume_response(resume)


@router.post("/match/{job_id}", response_model=ResumeMatchResponse)
async def match_resume_to_job(
    user_id: str,
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Match user's resume against a specific job and return match score."""
    # Get resume
    resume_result = await session.execute(select(ResumeData).where(ResumeData.user_id == user_id))
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Upload a resume first.")

    # Get job (column-only select — avoids eager relationship joins that
    # crash against the live interntrack schema).
    job_result = await session.execute(
        select(
            Job.id,
            Job.title,
            Job.company,
            Job.required_skills,
            Job.preferred_skills,
            Job.tags,
        ).where(Job.id == job_id)
    )
    row = job_result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = _JobMatchData(*row)

    # Extract resume skill names
    resume_skills = _extract_skill_names(resume.skills)

    # Calculate match using shared helper
    match_response = _calculate_job_match(resume_skills, job)

    # Store match result
    match_result = ResumeMatchResult(
        resume_id=resume.id,
        job_id=job_id,
        match_score=match_response.match_score,
        matched_skills=match_response.matched_skills,
        missing_skills=match_response.missing_skills,
        suggestions=match_response.suggestions,
    )
    session.add(match_result)
    await session.flush()

    return match_response


@router.delete("/{user_id}")
async def delete_resume(user_id: str, session: AsyncSession = Depends(get_session)):
    """Delete the user's resume data."""
    result = await session.execute(select(ResumeData).where(ResumeData.user_id == user_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found for this user.")
    await session.delete(resume)
    await session.flush()
    return {"message": "Resume deleted successfully"}


@router.post("/match-batch", response_model=ResumeBatchMatchResponse)
async def match_resume_batch(
    user_id: str,
    job_ids: List[str] = Query(..., min_length=1, max_length=50),
    session: AsyncSession = Depends(get_session),
):
    """Match user's resume against multiple jobs and return match scores."""
    # Enforce batch size limit
    if len(job_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 jobs per batch request.")

    # Get resume
    resume_result = await session.execute(select(ResumeData).where(ResumeData.user_id == user_id))
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Upload a resume first.")

    # Get all jobs (column-only select — avoids eager relationship joins
    # that crash against the live interntrack schema).
    job_result = await session.execute(
        select(
            Job.id,
            Job.title,
            Job.company,
            Job.required_skills,
            Job.preferred_skills,
            Job.tags,
        ).where(Job.id.in_(job_ids))
    )
    jobs = {str(row.id): _JobMatchData(*row) for row in job_result.all()}

    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found.")

    # Extract resume skill names
    resume_skills = _extract_skill_names(resume.skills)

    matches = []
    scores = []

    for job_id in job_ids:
        job = jobs.get(job_id)
        if not job:
            continue

        # Calculate match using shared helper
        match_response = _calculate_job_match(resume_skills, job)

        # Store match result
        match_result = ResumeMatchResult(
            resume_id=resume.id,
            job_id=job_id,
            match_score=match_response.match_score,
            matched_skills=match_response.matched_skills,
            missing_skills=match_response.missing_skills,
            suggestions=match_response.suggestions,
        )
        session.add(match_result)

        if match_response.match_score is not None:
            scores.append(match_response.match_score)

        matches.append(match_response)

    await session.flush()

    # Sort by match score (descending)
    matches.sort(key=lambda m: m.match_score or 0, reverse=True)

    return ResumeBatchMatchResponse(
        user_id=user_id,
        total_jobs_matched=len(matches),
        matches=matches,
        top_match=matches[0] if matches else None,
        average_score=round(sum(scores) / len(scores), 1) if scores else None,
    )
