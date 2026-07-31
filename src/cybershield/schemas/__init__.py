"""
CyberGuide Schemas Package

Pydantic models for API request/response validation.
"""

from .job import JobCreate, JobUpdate, JobResponse, JobListResponse
from .application import ApplicationCreate, ApplicationUpdate, ApplicationResponse, ApplicationStatusUpdate, ApplicationMetrics
from .user import UserCreate, UserUpdate, UserResponse, CompanyWatchlistCreate, KeywordWatchlistCreate
from .analytics import SkillTrendResponse, MarketInsight
from .notification import NotificationConfig, NotificationTest, NotificationResponse

__all__ = [
    "JobCreate", "JobUpdate", "JobResponse", "JobListResponse",
    "ApplicationCreate", "ApplicationUpdate", "ApplicationResponse", "ApplicationStatusUpdate", "ApplicationMetrics",
    "UserCreate", "UserUpdate", "UserResponse", "CompanyWatchlistCreate", "KeywordWatchlistCreate",
    "SkillTrendResponse", "MarketInsight",
    "NotificationConfig", "NotificationTest", "NotificationResponse",
]
