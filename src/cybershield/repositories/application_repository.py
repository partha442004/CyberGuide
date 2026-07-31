"""
Application Repository

Specialized repository for application tracking operations.
"""

from typing import Optional, Sequence
from datetime import datetime, timezone

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cybershield.domain.models import Application, ApplicationStatusHistory, Job
from cybershield.domain.enums import ApplicationStatus
from cybershield.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):
    """Repository for Application tracking operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Application, session)

    async def get_with_job(self, id: str) -> Optional[Application]:
        """Get application with job details."""
        result = await self.session.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self, user_id: str, status: ApplicationStatus
    ) -> Sequence[Application]:
        """Get all applications with a specific status."""
        result = await self.session.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(
                and_(
                    Application.user_id == user_id,
                    Application.status == status,
                )
            )
            .order_by(desc(Application.updated_at))
        )
        return result.scalars().all()

    async def get_user_applications(
        self,
        user_id: str,
        status: Optional[ApplicationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Application]:
        """Get all applications for a user with optional status filter."""
        query = (
            select(Application)
            .options(selectinload(Application.job))
            .where(Application.user_id == user_id)
        )

        if status:
            query = query.where(Application.status == status)

        query = query.order_by(desc(Application.updated_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_status(
        self,
        application_id: str,
        new_status: ApplicationStatus,
        notes: Optional[str] = None,
    ) -> Application:
        """Update application status and create history record."""
        application = await self.get_or_raise(application_id)
        old_status = application.status

        # Update status
        status_val = new_status.value if hasattr(new_status, 'value') else str(new_status)
        application.status = status_val
        if notes:
            application.notes = (application.notes or "") + f"\n\n{status_val}: {notes}"

        # Create history record
        history = ApplicationStatusHistory(
            application_id=application_id,
            old_status=old_status,
            new_status=status_val,
            notes=notes,
        )
        self.session.add(history)

        await self.session.flush()
        return application

    async def get_status_history(self, application_id: str) -> Sequence[ApplicationStatusHistory]:
        """Get status change history for an application."""
        result = await self.session.execute(
            select(ApplicationStatusHistory)
            .where(ApplicationStatusHistory.application_id == application_id)
            .order_by(desc(ApplicationStatusHistory.created_at))
        )
        return result.scalars().all()

    async def get_application_metrics(self, user_id: str) -> dict:
        """Get application metrics for a user."""
        # Count by status
        status_counts = {}
        for status in ApplicationStatus:
            result = await self.session.execute(
                select(func.count())
                .where(
                    and_(
                        Application.user_id == user_id,
                        Application.status == status,
                    )
                )
            )
            status_counts[status.value] = result.scalar()

        # Total applications
        total_result = await self.session.execute(
            select(func.count())
            .where(Application.user_id == user_id)
        )
        total = total_result.scalar()

        # Success rate (interviews / total)
        interviews = status_counts.get("interview", 0) + status_counts.get("offer", 0) + status_counts.get("joined", 0)
        success_rate = (interviews / total * 100) if total > 0 else 0

        return {
            "total": total,
            "by_status": status_counts,
            "success_rate": round(success_rate, 1),
        }

    async def get_upcoming_deadlines(self, user_id: str, days: int = 7) -> Sequence[Application]:
        """Get applications with upcoming interview deadlines."""
        now = datetime.now(timezone.utc)
        future = datetime.now(timezone.utc).replace(day=now.day + days)

        result = await self.session.execute(
            select(Application)
            .options(selectinload(Application.job))
            .where(
                and_(
                    Application.user_id == user_id,
                    Application.status.in_([
                        ApplicationStatus.INTERVIEW.value,
                        ApplicationStatus.ASSESSMENT.value,
                    ]),
                    Application.interview_at <= future,
                    Application.interview_at >= now,
                )
            )
            .order_by(Application.interview_at)
        )
        return result.scalars().all()
