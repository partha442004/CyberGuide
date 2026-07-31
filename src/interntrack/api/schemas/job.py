"""
Job API schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    """Base job schema."""
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=200)
    location: Optional[str] = None
    description: Optional[str] = None
    url: str = Field(..., max_length=2000)
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    is_remote: bool = False
    tags: List[str] = []


class JobCreate(JobBase):
    """Schema for creating a job."""
    source: str = "manual"


class JobUpdate(BaseModel):
    """Schema for updating a job."""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    is_remote: Optional[bool] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class JobResponse(JobBase):
    """Schema for job response."""
    id: str
    source: str
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Schema for job list response."""
    jobs: List[JobResponse]
    total: int
    skip: int
    limit: int


class JobSearchRequest(BaseModel):
    """Schema for job search request."""
    query: str = Field(..., min_length=1)
    location: Optional[str] = None
    job_type: Optional[str] = None
    is_remote: Optional[bool] = None
    limit: int = Field(50, ge=1, le=200)


class CompanyStat(BaseModel):
    """Company statistic."""
    company: str
    jobs: int


class JobTypeStat(BaseModel):
    """Job type statistic."""
    type: str
    count: int


class JobStatistics(BaseModel):
    """Schema for job statistics."""
    total_jobs: int
    salary_stats: dict
    top_companies: List[CompanyStat]
    job_types: List[JobTypeStat]
