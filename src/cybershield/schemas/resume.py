"""
Resume Schemas

Pydantic models for resume upload and parsing API operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SkillItem(BaseModel):
    """A single skill extracted from resume."""

    name: str
    category: str
    confidence: float = 0.9


class EducationItem(BaseModel):
    """Education information."""

    degree: Optional[str] = None
    institution: Optional[str] = None
    gpa: Optional[str] = None
    years: Optional[str] = None


class ExperienceItem(BaseModel):
    """Work experience item."""

    role: str
    context: Optional[str] = None


class CertificationItem(BaseModel):
    """Certification information."""

    name: str
    status: str = "completed"
    context: Optional[str] = None


class ProjectItem(BaseModel):
    """Project information."""

    name: str
    description: Optional[str] = None
    technologies: List[str] = []


class ResumeUploadResponse(BaseModel):
    """Response after uploading and parsing a resume."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    file_name: Optional[str] = None
    file_hash: str
    skills: List[Dict[str, Any]] = []
    education: List[Dict[str, Any]] = []
    experience: List[Dict[str, Any]] = []
    certifications: List[Dict[str, Any]] = []
    projects: List[Dict[str, Any]] = []
    links: Dict[str, str] = {}
    parsed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ResumeMatchResponse(BaseModel):
    """Response for resume-job matching."""

    job_id: str
    job_title: str
    company: str
    match_score: Optional[float] = None
    matched_skills: List[str] = []
    related_skills: List[str] = []
    missing_skills: List[str] = []
    suggestions: List[str] = []
    ats_score: Optional[float] = None
    ats_feedback: List[str] = []


class ResumeMatchRequest(BaseModel):
    """Request to match resume against specific job."""

    resume_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)


class ResumeBatchMatchResponse(BaseModel):
    """Response for batch resume-job matching."""

    user_id: str
    total_jobs_matched: int
    matches: List[ResumeMatchResponse] = []
    top_match: Optional[ResumeMatchResponse] = None
    average_score: Optional[float] = None


class CoverLetterResponse(BaseModel):
    """Generated cover letter for a specific job."""

    job_id: str
    job_title: str
    company: str
    cover_letter: str
    match_score: Optional[float] = None
    matched_skills: List[str] = []


class InterviewPrepQuestion(BaseModel):
    """A single interview-prep question with its theme."""

    category: str
    question: str


class InterviewPrepResponse(BaseModel):
    """Generated interview-prep shortlist for a specific job."""

    job_id: str
    job_title: str
    company: str
    questions: List[InterviewPrepQuestion] = []
    tips: List[str] = []
    match_score: Optional[float] = None
