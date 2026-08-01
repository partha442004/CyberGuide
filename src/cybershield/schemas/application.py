"""
Application Schemas

Pydantic models for application tracking API operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApplicationBase(BaseModel):
    """Base application schema with common fields."""

    user_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    status: str = "saved"
    notes: Optional[str] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None


class ApplicationCreate(ApplicationBase):
    """Schema for creating a new application."""

    id: Optional[str] = None
    applied_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""

    status: Optional[str] = None
    notes: Optional[str] = None
    interview_at: Optional[datetime] = None


class ApplicationStatusUpdate(BaseModel):
    """Schema for updating application status."""

    status: str
    notes: Optional[str] = None


class ApplicationResponse(ApplicationBase):
    """Schema for application response."""

    id: str
    applied_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationMetrics(BaseModel):
    """Schema for application metrics."""

    total: int
    by_status: dict
    success_rate: float
