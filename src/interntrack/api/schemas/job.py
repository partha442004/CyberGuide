"""
Job API schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class JobShareRequest(BaseModel):
    """Schema for sharing/saving a job from a link the user found.

    Only ``url`` is required. When ``title``/``company`` are omitted the API
    fetches the page and auto-detects them from its OpenGraph meta tags (so a
    LinkedIn post, company careers page, or any job board link can be saved
    without typing anything).
    """

    url: str = Field(..., max_length=2000)
    title: str | None = Field(None, min_length=1, max_length=500)
    company: str | None = Field(None, min_length=1, max_length=200)
    location: str | None = Field(None, max_length=200)
    description: str | None = None


class JobImportLinksRequest(BaseModel):
    """Schema for bulk-importing multiple job links at once.

    Accepts up to ``MAX_LINKS`` URLs (kept small so the whole batch fits
    inside the platform's request timeout); each link is processed exactly
    like a single ``/jobs/share`` call — title/company auto-detected from
    the page, duplicates skipped. Results are reported per link so the UI
    can show exactly which links saved, which were duplicates, and which
    failed.
    """

    urls: list[str] = Field(..., min_length=1, max_length=8)

    @field_validator("urls")
    @classmethod
    def _strip_and_validate(cls, v: list[str]) -> list[str]:
        cleaned = [u.strip() for u in v if u and u.strip()]
        if not cleaned:
            raise ValueError("At least one valid URL is required.")
        for u in cleaned:
            if not u.startswith(("http://", "https://")):
                raise ValueError(f"'{u[:40]}' is not a valid http(s) URL.")
            if len(u) > 2000:
                raise ValueError("URLs must be 2000 characters or fewer.")
        return cleaned


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
    view_count: int = 0
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
