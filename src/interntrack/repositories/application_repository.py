"""
Application repository with application-specific queries.
"""

from datetime import timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import ApplicationStatus
from interntrack.domain.models import Application
from interntrack.repositories.base import BaseRepository
from interntrack.utils.helpers import utcnow


class ApplicationRepository(BaseRepository[Application]):
    """Application repository with application-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(Application, session)

    @staticmethod
    def _user_filter(user_id: str | None):
        """Optional user scoping for queries (None = all users / legacy)."""
        if user_id:
            return Application.user_id == user_id
        return None

    async def get_by_job_id(self, job_id: str) -> Application | None:
        """Get application by job ID (legacy, any user)."""
        result = await self.session.execute(
            select(Application).where(Application.job_id == job_id),
        )
        return result.scalar_one_or_none()

    async def get_by_job_id_for_user(
        self,
        job_id: str,
        user_id: str,
    ) -> Application | None:
        """Get a user's application for a job (dedupe Apply per user)."""
        result = await self.session.execute(
            select(Application).where(
                Application.job_id == job_id,
                Application.user_id == user_id,
            ),
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        status: ApplicationStatus,
        user_id: str | None = None,
    ) -> list[Application]:
        """Get all applications with a specific status (optionally per user)."""
        filters = [Application.status == status]
        user_filter = self._user_filter(user_id)
        if user_filter is not None:
            filters.append(user_filter)
        result = await self.session.execute(select(Application).where(*filters))
        return list(result.scalars().all())

    async def get_applied_job_ids(self) -> set[str]:
        """Return the job IDs that have at least one application tracked."""
        result = await self.session.execute(select(Application.job_id))
        return {str(job_id) for (job_id,) in result.all()}

    async def get_status_counts(
        self,
        user_id: str | None = None,
    ) -> dict[str, int]:
        """Get count of applications by status (optionally per user)."""
        query = select(Application.status, func.count(Application.id))
        user_filter = self._user_filter(user_id)
        if user_filter is not None:
            query = query.where(user_filter)
        query = query.group_by(Application.status)
        result = await self.session.execute(query)
        # Use .value (lowercase) to keep the same key casing as the enum values
        # that clients previously received after JSON encoding.
        return {status.value: count for status, count in result.all()}

    async def get_recent_applications(
        self,
        days: int = 30,
        user_id: str | None = None,
    ) -> list[Application]:
        """Get applications from the last N days (optionally per user)."""
        cutoff_date = utcnow() - timedelta(days=days)
        filters = [Application.created_at >= cutoff_date]
        user_filter = self._user_filter(user_id)
        if user_filter is not None:
            filters.append(user_filter)
        query = (
            select(Application).where(*filters).order_by(Application.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_application_timeline(
        self,
        days: int = 30,
        user_id: str | None = None,
    ) -> list[dict]:
        """Get application timeline for charts (optionally per user)."""
        cutoff_date = utcnow() - timedelta(days=days)
        query = select(
            func.date(Application.created_at).label("date"),
            Application.status,
            func.count(Application.id).label("count"),
        ).where(Application.created_at >= cutoff_date)
        user_filter = self._user_filter(user_id)
        if user_filter is not None:
            query = query.where(user_filter)
        query = query.group_by(
            func.date(Application.created_at), Application.status
        ).order_by(func.date(Application.created_at))
        result = await self.session.execute(query)
        return [
            {"date": str(row.date), "status": row.status, "count": row.count}
            for row in result.all()
        ]

    async def get_pending_reminders(self) -> list[Application]:
        """Get applications that need reminders."""
        query = select(Application).where(
            and_(
                Application.reminded.is_(False),
                Application.status.in_(
                    [
                        ApplicationStatus.APPLIED,
                        ApplicationStatus.INTERVIEW,
                    ],
                ),
            ),
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_priority_applications(
        self,
        min_priority: int = 1,
    ) -> list[Application]:
        """Get high-priority applications."""
        query = (
            select(Application)
            .where(Application.priority >= min_priority)
            .order_by(Application.priority.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        application_id: str,
        new_status: ApplicationStatus,
        notes: str | None = None,
    ) -> Application | None:
        """Update application status with history tracking."""
        from interntrack.domain.models import ApplicationStatusHistory

        application = await self.get_by_id(application_id)
        if not application:
            return None

        old_status = application.status
        application.status = new_status  # type: ignore[assignment]

        if new_status == ApplicationStatus.APPLIED and not application.applied_at:
            application.applied_at = utcnow()  # type: ignore[assignment]

        # Add status history entry
        history = ApplicationStatusHistory(
            application_id=application_id,
            old_status=old_status,
            new_status=new_status,
            notes=notes,
        )
        self.session.add(history)

        await self.session.flush()
        return application

    async def _count_by_status(
        self,
        status: ApplicationStatus,
        user_id: str | None = None,
    ) -> int:
        """Count applications with a status (optionally per user)."""
        query = select(func.count(Application.id)).where(Application.status == status)
        user_filter = self._user_filter(user_id)
        if user_filter is not None:
            query = query.where(user_filter)
        result = await self.session.execute(query)
        return int(result.scalar_one() or 0)

    async def get_rejection_rate(self, user_id: str | None = None) -> float:
        """Calculate rejection rate (optionally per user)."""
        total = await self.count_with_user(user_id)
        if total == 0:
            return 0.0
        rejected = await self._count_by_status(ApplicationStatus.REJECTED, user_id)
        return round(rejected / total * 100, 2)

    async def get_response_rate(self, user_id: str | None = None) -> float:
        """Calculate response rate (interviews / applications)."""
        applied = await self._count_by_status(ApplicationStatus.APPLIED, user_id)
        if applied == 0:
            return 0.0
        interviews = await self._count_by_status(ApplicationStatus.INTERVIEW, user_id)
        return round(interviews / applied * 100, 2)

    async def count_with_user(self, user_id: str | None = None) -> int:
        """Count applications (optionally per user)."""
        query = select(func.count()).select_from(Application)
        user_filter = self._user_filter(user_id)
        if user_filter is not None:
            query = query.where(user_filter)
        result = await self.session.execute(query)
        return int(result.scalar_one() or 0)
