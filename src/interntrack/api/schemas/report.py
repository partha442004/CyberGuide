"""
Report API schemas.
"""

from pydantic import BaseModel


class ReportSummary(BaseModel):
    """Report summary."""

    new_jobs: int = 0
    new_applications: int = 0
    total_applications: int = 0
    rejection_rate: float | None = None
    response_rate: float | None = None


class JobSummary(BaseModel):
    """Job summary in report."""

    title: str
    company: str
    location: str | None = None
    url: str | None = None
    posted_at: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    is_active: bool = True
    age_days: int = 0


class CompanySummary(BaseModel):
    """Company summary in report."""

    company: str
    jobs: int


class ReportResponse(BaseModel):
    """Report response."""

    report_type: str
    generated_at: str
    summary: ReportSummary
    new_jobs: list[JobSummary] = []
    closing_soon: list[JobSummary] = []
    top_companies: list[CompanySummary] = []
    job_type_distribution: list[dict] = []
    application_timeline: list[dict] = []
    application_status: dict = {}
    salary_statistics: dict | None = None


class ReportListResponse(BaseModel):
    """List of reports."""

    reports: list[ReportResponse]


class LearningResource(BaseModel):
    """Learning resource."""

    skill: str
    category: str
    resources: list[dict]


class LearningPathResponse(BaseModel):
    """Learning path response."""

    steps: list[dict]
    estimated_hours: int | None = None
    resources: list[LearningResource] = []
