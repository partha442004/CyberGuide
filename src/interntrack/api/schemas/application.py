"""
Application API schemas.
"""

from datetime import datetime

from pydantic import BaseModel


class ApplicationBase(BaseModel):
    """Base application schema."""

    job_id: str
    status: str = "saved"
    notes: str | None = None
    resume_version: str | None = None
    cover_letter: str | None = None
    priority: int = 0


class ApplicationCreate(BaseModel):
    """Schema for creating an application."""

    job_id: str
    user_id: str | None = None


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    status: str | None = None
    notes: str | None = None
    resume_version: str | None = None
    cover_letter: str | None = None
    priority: int | None = None


class ApplicationResponse(BaseModel):
    """Schema for application response."""

    id: str
    job_id: str
    user_id: str | None = None
    status: str
    applied_at: datetime | None = None
    interview_at: datetime | None = None
    notes: str | None = None
    resume_version: str | None = None
    priority: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationWithJob(ApplicationResponse):
    """Application response with job details."""

    job_title: str | None = None
    job_company: str | None = None
    job_url: str | None = None


class ApplicationListResponse(BaseModel):
    """Schema for application list response."""

    applications: list[ApplicationResponse]
    total: int


class FollowUpItem(BaseModel):
    """A pending follow-up application (applied/interview, not yet reminded)."""

    application_id: str
    job_id: str
    job_title: str | None = None
    company: str | None = None
    job_url: str | None = None
    status: str
    applied_at: datetime | None = None
    days_since: int


class FollowUpsResponse(BaseModel):
    """Pending follow-up applications, most urgent first."""

    follow_ups: list[FollowUpItem] = []


class ApplicationHistoryItem(BaseModel):
    """A single application status-change event."""

    status: str
    changed_at: datetime | None = None
    notes: str | None = None


class ApplicationHistoryResponse(BaseModel):
    """Status-change history for one application."""

    application_id: str
    history: list[ApplicationHistoryItem] = []


class ApplicationStatusUpdate(BaseModel):
    """Schema for status update."""

    status: str
    notes: str | None = None


class ApplicationMetrics(BaseModel):
    """Schema for application metrics."""

    total_applications: int
    status_counts: dict
    rejection_rate: float
    response_rate: float
    recent_applications: int


class ApplicationTimeline(BaseModel):
    """Schema for application timeline."""

    date: str
    status: str
    count: int
