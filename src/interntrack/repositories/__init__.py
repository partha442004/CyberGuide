"""Repository layer for data access."""

from interntrack.repositories.application_repository import ApplicationRepository
from interntrack.repositories.base import BaseRepository
from interntrack.repositories.job_repository import JobRepository
from interntrack.repositories.skill_repository import SkillRepository
from interntrack.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "JobRepository",
    "ApplicationRepository",
    "SkillRepository",
    "UserRepository",
]
