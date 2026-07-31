"""
Application API schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ApplicationBase(BaseModel):
    """Base application schema."""
    job_id: str
    status: str = "saved"
    notes: Optional[str] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None
    priority: int = 0


class ApplicationCreate(BaseModel):
    """Schema for creating an application."""
    job_id: str


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    status: Optional[str] = None
    notes: Optional[str] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None
    priority: Optional[int] = None


class ApplicationResponse(BaseModel):
    """Schema for application response."""
    id: str
    job_id: str
    status: str
    applied_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None
    notes: Optional[str] = None
    resume_version: Optional[str] = None
    priority: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationWithJob(ApplicationResponse):
    """Application response with job details."""
    job_title: Optional[str] = None
    job_company: Optional[str] = None
    job_url: Optional[str] = None


class ApplicationListResponse(BaseModel):
    """Schema for application list response."""
    applications: List[ApplicationResponse]
    total: int


class ApplicationStatusUpdate(BaseModel):
    """Schema for status update."""
    status: str
    notes: Optional[str] = None


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
