"""
CyberGuide Schemas Package

Pydantic models for API request/response validation.
"""

from .analytics import MarketInsight, SkillTrendResponse
from .application import (
    ApplicationCreate,
    ApplicationMetrics,
    ApplicationResponse,
    ApplicationStatusUpdate,
    ApplicationUpdate,
)
from .job import JobCreate, JobListResponse, JobResponse, JobUpdate
from .notification import NotificationConfig, NotificationResponse, NotificationTest
from .user import (
    CompanyWatchlistCreate,
    KeywordWatchlistCreate,
    UserCreate,
    UserResponse,
    UserUpdate,
)

__all__ = [
    "JobCreate",
    "JobUpdate",
    "JobResponse",
    "JobListResponse",
    "ApplicationCreate",
    "ApplicationUpdate",
    "ApplicationResponse",
    "ApplicationStatusUpdate",
    "ApplicationMetrics",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "CompanyWatchlistCreate",
    "KeywordWatchlistCreate",
    "SkillTrendResponse",
    "MarketInsight",
    "NotificationConfig",
    "NotificationTest",
    "NotificationResponse",
]
