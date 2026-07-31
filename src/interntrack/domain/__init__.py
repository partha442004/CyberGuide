"""Domain layer - Business entities and logic."""

from interntrack.domain.enums import (
    ApplicationStatus,
    JobType,
    ExperienceLevel,
    NotificationChannel,
    ReportType,
)
from interntrack.domain.exceptions import (
    AppException,
    NotFoundError,
    ScrapingError,
    NotificationError,
    DuplicateJobError,
)

__all__ = [
    "ApplicationStatus",
    "JobType",
    "ExperienceLevel",
    "NotificationChannel",
    "ReportType",
    "AppException",
    "NotFoundError",
    "ScrapingError",
    "NotificationError",
    "DuplicateJobError",
]
