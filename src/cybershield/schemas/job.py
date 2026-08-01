"""
Job Schemas

Pydantic models for job-related API operations.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobBase(BaseModel):
    """Base job schema with common fields."""

    title: str = Field(..., min_length=1, max_length=500)
    company: Optional[str] = None
    company_id: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    apply_url: Optional[str] = None
    source: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    is_remote: bool = False
    work_mode: Optional[str] = None
    duration: Optional[str] = None
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    required_skills: Optional[List[str]] = []
    preferred_skills: Optional[List[str]] = []
    benefits: Optional[List[str]] = []


class JobCreate(JobBase):
    """Schema for creating a new job."""

    id: Optional[str] = None
    job_id_external: Optional[str] = None
    source_url: Optional[str] = None
    eligibility: Optional[dict] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    cgpa_min: Optional[float] = None
    batch: Optional[str] = None
    openings: Optional[int] = None
    selection_process: Optional[str] = None
    interview_process: Optional[str] = None
    hr_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_linkedin: Optional[str] = None
    hiring_manager: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    scraped_at: Optional[datetime] = None
    raw_data: Optional[dict] = None


class JobUpdate(BaseModel):
    """Schema for updating a job."""

    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    apply_url: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class JobResponse(BaseModel):
    """Schema for job response."""

    id: str
    title: str
    company: Optional[str] = None
    company_id: Optional[str] = None
    department: Optional[str] = None
    job_id_external: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    apply_url: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    is_remote: bool = False
    work_mode: Optional[str] = None
    duration: Optional[str] = None
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    required_skills: Optional[List[str]] = []
    preferred_skills: Optional[List[str]] = []
    benefits: Optional[List[str]] = None
    eligibility: Optional[dict] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    cgpa_min: Optional[float] = None
    batch: Optional[str] = None
    selection_process: Optional[str] = None
    interview_process: Optional[str] = None
    hr_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_linkedin: Optional[str] = None
    hiring_manager: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """Schema for paginated job list response."""

    items: List[JobResponse]
    total: int
    skip: int
    limit: int
