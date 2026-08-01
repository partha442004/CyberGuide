"""
Job API schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    """Base job schema."""
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=200)
    location: str | None = None
    description: str | None = None
    url: str = Field(..., max_length=2000)
    job_type: str | None = None
    experience_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    is_remote: bool = False
    tags: list[str] = []


class JobCreate(JobBase):
    """Schema for creating a job."""
    source: str = "manual"


class JobUpdate(BaseModel):
    """Schema for updating a job."""
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    is_remote: bool | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class JobResponse(JobBase):
    """Schema for job response."""
    id: str
    source: str
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Schema for job list response."""
    jobs: list[JobResponse]
    total: int
    skip: int
    limit: int


class JobSearchRequest(BaseModel):
    """Schema for job search request."""
    query: str = Field(..., min_length=1)
    location: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
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
    top_companies: list[CompanyStat]
    job_types: list[JobTypeStat]
