"""
Resumes API Router

Endpoints for resume upload, parsing, matching, and skill extraction.
"""

from datetime import datetime, timezone
from typing import List

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
from cybershield.services.resume_service import ResumeParser

router = APIRouter()

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024


def _serialize_resume_response(resume: ResumeData) -> ResumeUploadResponse:
    """Helper to serialize ResumeData to response model."""
    return ResumeUploadResponse(
        id=resume.id,
        user_id=resume.user_id,
        file_name=resume.file_path,
        file_hash=resume.file_hash,
        skills=[s for s in (resume.skills or []) if s],
        education=[e for e in (resume.education or []) if e],
        experience=[x for x in (resume.experience or []) if x],
        certifications=[c for c in (resume.certifications or []) if c],
        projects=[p for p in (resume.projects or []) if p],
        links={"github": resume.github_url or "", "linkedin": resume.linkedin_url or ""},
        parsed_at=resume.parsed_at,
    )


def _extract_skill_names(skills_list) -> set:
    """Extract lowercase skill names from a list of skills."""
    result = set()
    for s in (skills_list or []):
        if isinstance(s, str) and s:
            result.add(s.lower())
        elif isinstance(s, dict):
            name = s.get("name", "")
            if name:
                result.add(name.lower())
    return result


def _calculate_job_match(resume_skills: set, job: Job) -> ResumeMatchResponse:
    """Calculate match score between resume skills and a job."""
    job_required = _extract_skill_names(job.required_skills)
    job_preferred = _extract_skill_names(job.preferred_skills)
    all_job_skills = job_required | job_preferred

    if not all_job_skills:
        match_score = None
        matched = []
        missing = []
    else:
        matched = list(resume_skills & all_job_skills)
        missing = list(all_job_skills - resume_skills)

        req_total = max(len(job_required), 1)
        pref_total = max(len(job_preferred), 1)
        required_matched = len(resume_skills & job_required)
        preferred_matched = len(resume_skills & job_preferred)

        match_score = round(
            (required_matched / req_total * 0.7 + preferred_matched / pref_total * 0.3) * 100,
            1,
        )

    suggestions = []
    if missing:
        suggestions.append(f"Learn missing skills: {', '.join(missing[:5])}")
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

    existing = await session.execute(
        select(ResumeData).where(ResumeData.user_id == user_id)
    )
    existing_resume = existing.scalar_one_or_none()
    skills_data = parsed_data.get("skills", [])

    if existing_resume:
        existing_resume.file_path = file.filename
        existing_resume.file_hash = parsed_data["file_hash"]
        existing_resume.skills = skills_data
        existing_resume.education = parsed_data.get("education", [])
        existing_resume.experience = parsed_data.get("experience", [])
        existing_resume.projects = parsed_data.get("projects", [])
        existing_resume.certifications = parsed_data.get("certifications", [])
        existing_resume.github_url = parsed_data.get("links", {}).get("github")
        existing_resume.linkedin_url = parsed_data.get("links", {}).get("linkedin")
        existing_resume.parsed_at = datetime.now(timezone.utc)
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
            parsed_at=datetime.now(timezone.utc),
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
    resume_result = await session.execute(
        select(ResumeData).where(ResumeData.user_id == user_id)
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Upload a resume first.")

    # Get job
    job_result = await session.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

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
    resume_result = await session.execute(
        select(ResumeData).where(ResumeData.user_id == user_id)
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Upload a resume first.")

    # Get all jobs
    job_result = await session.execute(
        select(Job).where(Job.id.in_(job_ids))
    )
    jobs = {job.id: job for job in job_result.scalars().all()}

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
