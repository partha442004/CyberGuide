"""
Report API schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ReportSummary(BaseModel):
    """Report summary."""
    new_jobs: int = 0
    new_applications: int = 0
    total_applications: int = 0
    rejection_rate: Optional[float] = None
    response_rate: Optional[float] = None


class JobSummary(BaseModel):
    """Job summary in report."""
    title: str
    company: str
    location: Optional[str] = None
    url: Optional[str] = None
    expires_at: Optional[str] = None


class CompanySummary(BaseModel):
    """Company summary in report."""
    company: str
    jobs: int


class ReportResponse(BaseModel):
    """Report response."""
    report_type: str
    generated_at: str
    summary: ReportSummary
    new_jobs: List[JobSummary] = []
    closing_soon: List[JobSummary] = []
    top_companies: List[CompanySummary] = []
    job_type_distribution: List[dict] = []
    application_timeline: List[dict] = []
    application_status: dict = {}
    salary_statistics: Optional[dict] = None


class ReportListResponse(BaseModel):
    """List of reports."""
    reports: List[ReportResponse]


class LearningResource(BaseModel):
    """Learning resource."""
    skill: str
    category: str
    resources: List[dict]


class LearningPathResponse(BaseModel):
    """Learning path response."""
    steps: List[dict]
    estimated_hours: Optional[int] = None
    resources: List[LearningResource] = []
