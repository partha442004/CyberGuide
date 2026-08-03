"""
SQLAlchemy ORM models for the application.
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, relationship, validates

from interntrack.domain.enums import (
    ApplicationStatus,
    ExperienceLevel,
    JobSource,
    JobType,
    SkillCategory,
)
from interntrack.utils.helpers import to_naive_utc, utcnow


class Base(DeclarativeBase):
    """Base model for all database models."""


class TimestampMixin:
    """Mixin for timestamp fields."""

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class Job(Base, TimestampMixin):
    """Job listing model."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title = Column(String(500), nullable=False)
    company = Column(String(200), nullable=False, index=True)
    location = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(2000), nullable=False, unique=True)
    source: Column = Column(
        Enum(
            JobSource,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=JobSource.UNKNOWN,
    )
    job_type: Column = Column(
        Enum(
            JobType,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=JobType.UNKNOWN,
    )
    experience_level: Column = Column(
        Enum(
            ExperienceLevel,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), nullable=True, default="USD")
    is_remote = Column(Boolean, default=False)
    posted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True, default=list)
    raw_data = Column(JSON, nullable=True)

    # Relationships
    applications = relationship("Application", back_populates="job", lazy="selectin")
    skills = relationship("JobSkill", back_populates="job", lazy="selectin")

    __table_args__ = (
        Index("idx_job_company", "company"),
        Index("idx_job_source", "source"),
        Index("idx_job_active", "is_active"),
    )

    @validates("posted_at", "expires_at")
    def _coerce_naive_utc(self, _key: str, value):
        """Normalize aware datetimes to naive UTC for Postgres binding."""
        return to_naive_utc(value)

    def __repr__(self) -> str:
        return f"<Job {self.title} at {self.company}>"


class Application(Base, TimestampMixin):
    """Job application tracking model."""

    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    status: Column = Column(
        Enum(
            ApplicationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ApplicationStatus.SAVED,
    )
    applied_at = Column(DateTime, nullable=True)
    interview_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    resume_version = Column(String(100), nullable=True)
    cover_letter = Column(Text, nullable=True)
    priority = Column(Integer, default=0)
    reminded = Column(Boolean, default=False)

    @validates("applied_at", "interview_at")
    def _coerce_naive_utc(self, _key: str, value):
        """Normalize aware datetimes to naive UTC for Postgres binding."""
        return to_naive_utc(value)

    # Relationships
    job = relationship("Job", back_populates="applications")
    status_history = relationship(
        "ApplicationStatusHistory",
        back_populates="application",
        lazy="selectin",
        order_by="ApplicationStatusHistory.created_at",
    )

    __table_args__ = (
        Index("idx_application_status", "status"),
        Index("idx_application_job", "job_id"),
    )

    def __repr__(self) -> str:
        return f"<Application {self.status} for {self.job_id}>"


class ApplicationStatusHistory(Base, TimestampMixin):
    """Application status change history."""

    __tablename__ = "application_status_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id = Column(
        String(36),
        ForeignKey("applications.id"),
        nullable=False,
    )
    old_status: Column = Column(
        Enum(
            ApplicationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    new_status: Column = Column(
        Enum(
            ApplicationStatus,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    changed_at = Column(DateTime, default=utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="status_history")


class Skill(Base, TimestampMixin):
    """Skill model for learning recommendations."""

    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    category: Column = Column(
        Enum(
            SkillCategory,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    description = Column(Text, nullable=True)
    difficulty_level = Column(Integer, default=1)  # 1-5
    learning_resources = Column(JSON, nullable=True, default=list)
    is_active = Column(Boolean, default=True)

    # Relationships
    user_skills = relationship("UserSkill", back_populates="skill")
    job_skills = relationship("JobSkill", back_populates="skill")

    __table_args__ = (Index("idx_skill_name", "name", unique=True),)

    def __repr__(self) -> str:
        return f"<Skill {self.name}>"


class JobSkill(Base):
    """Many-to-many relationship between jobs and skills."""

    __tablename__ = "job_skills"

    job_id = Column(String(36), ForeignKey("jobs.id"), primary_key=True)
    skill_id = Column(String(36), ForeignKey("skills.id"), primary_key=True)
    importance = Column(Integer, default=1)  # 1-5 scale

    # Relationships
    job = relationship("Job", back_populates="skills")
    skill = relationship("Skill", back_populates="job_skills")


class UserSkill(Base, TimestampMixin):
    """User skill proficiency tracking."""

    __tablename__ = "user_skills"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id = Column(
        String(36),
        ForeignKey("skills.id"),
        primary_key=True,
    )
    proficiency_level = Column(Integer, default=1)  # 1-5
    last_used = Column(DateTime, nullable=True)
    is_learning = Column(Boolean, default=False)

    @validates("last_used")
    def _coerce_naive_utc(self, _key: str, value):
        """Normalize aware datetimes to naive UTC for Postgres binding."""
        return to_naive_utc(value)

    # Relationships
    skill = relationship("Skill", back_populates="user_skills")


class LearningPath(Base, TimestampMixin):
    """Learning path for skill development."""

    __tablename__ = "learning_paths"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    skill_id = Column(String(36), ForeignKey("skills.id"), nullable=False)
    resources = Column(JSON, nullable=False, default=list)
    estimated_hours = Column(Integer, nullable=True)
    difficulty_level = Column(Integer, default=1)
    platform = Column(String(50), nullable=True)  # google_cloud, owasp, etc.

    __table_args__ = (Index("idx_learning_skill", "skill_id"),)


class NotificationConfig(Base, TimestampMixin):
    """User notification configuration."""

    __tablename__ = "notification_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    channel = Column(String(50), nullable=False, unique=True)
    is_enabled = Column(Boolean, default=True)
    config = Column(JSON, nullable=False, default=dict)
    last_notified = Column(DateTime, nullable=True)

    @validates("last_notified")
    def _coerce_naive_utc(self, _key: str, value):
        """Normalize aware datetimes to naive UTC for Postgres binding."""
        return to_naive_utc(value)


class ScheduledReport(Base, TimestampMixin):
    """Scheduled report configuration."""

    __tablename__ = "scheduled_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_type = Column(String(50), nullable=False)
    frequency = Column(String(50), nullable=False)  # daily, weekly, monthly
    is_enabled = Column(Boolean, default=True)
    last_generated = Column(DateTime, nullable=True)
    next_generation = Column(DateTime, nullable=True)
    recipients = Column(JSON, nullable=False, default=list)

    @validates("last_generated", "next_generation")
    def _coerce_naive_utc(self, _key: str, value):
        """Normalize aware datetimes to naive UTC for Postgres binding."""
        return to_naive_utc(value)


class Company(Base, TimestampMixin):
    """Company information for tracking."""

    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False, unique=True)
    website = Column(String(500), nullable=True)
    industry = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)  # startup, small, medium, large
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, default=0)
    is_watched = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True, default=list)

    __table_args__ = (Index("idx_company_name", "name", unique=True),)


class Bookmark(Base, TimestampMixin):
    """User bookmarks for jobs or companies."""

    __tablename__ = "bookmarks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_type = Column(String(50), nullable=False)  # job, company, skill
    item_id = Column(String(36), nullable=False)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True, default=list)

    __table_args__ = (Index("idx_bookmark_item", "item_type", "item_id"),)


class Watchlist(Base, TimestampMixin):
    """Keyword and company watchlists."""

    __tablename__ = "watchlists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    watch_type = Column(String(50), nullable=False)  # keyword, company
    value = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    notification_channels = Column(JSON, nullable=True, default=list)

    __table_args__ = (Index("idx_watchlist_type_value", "watch_type", "value"),)


class ActivityLog(Base, TimestampMixin):
    """Activity log for user actions."""

    __tablename__ = "activity_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    details = Column(JSON, nullable=True)

    __table_args__ = (Index("idx_activity_entity", "entity_type", "entity_id"),)
