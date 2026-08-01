"""Domain layer - Business entities and logic."""

from interntrack.domain.enums import (
    ApplicationStatus,
    ExperienceLevel,
    JobType,
    NotificationChannel,
    ReportType,
)
from interntrack.domain.exceptions import (
    AppException,
    DuplicateJobError,
    NotFoundError,
    NotificationError,
    ScrapingError,
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
