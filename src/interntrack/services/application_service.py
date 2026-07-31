"""
Application service for tracking job applications.
"""

from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import ApplicationStatus
from interntrack.domain.models import Application
from interntrack.repositories.application_repository import ApplicationRepository


class ApplicationService:
    """Application service for tracking applications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.app_repo = ApplicationRepository(session)

    async def create_application(
        self, job_id: str, status: ApplicationStatus = ApplicationStatus.SAVED
    ) -> Application:
        """Create a new application."""
        application = Application(job_id=job_id, status=status)
        return await self.app_repo.create(application)

    async def get_application(self, application_id: str) -> Optional[Application]:
        """Get an application by ID."""
        return await self.app_repo.get_by_id(application_id)

    async def get_application_for_job(self, job_id: str) -> Optional[Application]:
        """Get application for a specific job."""
        return await self.app_repo.get_by_job_id(job_id)

    async def update_status(
        self,
        application_id: str,
        new_status: ApplicationStatus,
        notes: Optional[str] = None,
    ) -> Optional[Application]:
        """Update application status."""
        return await self.app_repo.update_status(application_id, new_status, notes)

    async def get_applications_by_status(
        self, status: ApplicationStatus
    ) -> List[Application]:
        """Get all applications with a specific status."""
        return await self.app_repo.get_by_status(status)

    async def get_status_counts(self) -> Dict[str, int]:
        """Get count of applications by status."""
        return await self.app_repo.get_status_counts()

    async def get_application_timeline(self, days: int = 30) -> List[dict]:
        """Get application timeline for charts."""
        return await self.app_repo.get_application_timeline(days)

    async def get_metrics(self) -> dict:
        """Get application metrics."""
        status_counts = await self.get_status_counts()
        total = sum(status_counts.values())

        return {
            "total_applications": total,
            "status_counts": status_counts,
            "rejection_rate": await self.app_repo.get_rejection_rate(),
            "response_rate": await self.app_repo.get_response_rate(),
            "recent_applications": len(
                await self.app_repo.get_recent_applications(days=7)
            ),
        }

    async def mark_reminded(self, application_id: str) -> None:
        """Mark application as reminded."""
        application = await self.app_repo.get_by_id(application_id)
        if application:
            application.reminded = True
            await self.session.flush()

    async def get_pending_reminders(self) -> List[Application]:
        """Get applications needing reminders."""
        return await self.app_repo.get_pending_reminders()

    async def set_priority(self, application_id: str, priority: int) -> Optional[Application]:
        """Set application priority."""
        return await self.app_repo.update(application_id, {"priority": priority})
