"""
Application service for tracking job applications.
"""

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
        self,
        job_id: str,
        status: ApplicationStatus = ApplicationStatus.SAVED,
        user_id: str | None = None,
    ) -> Application:
        """Create a new application (optionally owned by a user)."""
        application = Application(job_id=job_id, status=status, user_id=user_id)
        return await self.app_repo.create(application)

    async def get_application(self, application_id: str) -> Application | None:
        """Get an application by ID."""
        return await self.app_repo.get_by_id(application_id)

    async def get_application_for_job(
        self,
        job_id: str,
        user_id: str | None = None,
    ) -> Application | None:
        """Get application for a specific job (per user when given)."""
        if user_id:
            return await self.app_repo.get_by_job_id_for_user(job_id, user_id)
        return await self.app_repo.get_by_job_id(job_id)

    async def update_status(
        self,
        application_id: str,
        new_status: ApplicationStatus,
        notes: str | None = None,
    ) -> Application | None:
        """Update application status."""
        return await self.app_repo.update_status(application_id, new_status, notes)

    async def get_applications_by_status(
        self,
        status: ApplicationStatus,
        user_id: str | None = None,
    ) -> list[Application]:
        """Get all applications with a specific status (optionally per user)."""
        return await self.app_repo.get_by_status(status, user_id=user_id)

    async def get_status_counts(self, user_id: str | None = None) -> dict[str, int]:
        """Get count of applications by status (optionally per user)."""
        return await self.app_repo.get_status_counts(user_id=user_id)

    async def get_application_timeline(
        self,
        days: int = 30,
        user_id: str | None = None,
    ) -> list[dict]:
        """Get application timeline for charts (optionally per user)."""
        return await self.app_repo.get_application_timeline(days, user_id=user_id)

    async def get_metrics(self, user_id: str | None = None) -> dict:
        """Get application metrics (optionally scoped to one user)."""
        status_counts = await self.get_status_counts(user_id=user_id)
        total = sum(status_counts.values())

        return {
            "total_applications": total,
            "status_counts": status_counts,
            "rejection_rate": await self.app_repo.get_rejection_rate(user_id=user_id),
            "response_rate": await self.app_repo.get_response_rate(user_id=user_id),
            "recent_applications": len(
                await self.app_repo.get_recent_applications(days=7, user_id=user_id),
            ),
        }

    async def mark_reminded(self, application_id: str) -> None:
        """Mark application as reminded."""
        application = await self.app_repo.get_by_id(application_id)
        if application:
            application.reminded = True  # type: ignore[assignment]
            await self.session.flush()

    async def get_pending_reminders(self) -> list[Application]:
        """Get applications needing reminders."""
        return await self.app_repo.get_pending_reminders()

    async def set_priority(
        self,
        application_id: str,
        priority: int,
    ) -> Application | None:
        """Set application priority."""
        return await self.app_repo.update(application_id, {"priority": priority})
