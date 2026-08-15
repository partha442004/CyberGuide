"""
SQLAlchemy ORM models for the application.
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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
from sqlalchemy.types import TypeDecorator

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

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class LenientEnum(TypeDecorator):
    """Enum-backed column that tolerates legacy stored values.

    SQLAlchemy's ``Enum`` (``validate_strings=False``, the default) stores
    any string on bind but raises on *load* for a value outside the enum
    class. Rows saved before label normalization existed (e.g. a scraper's
    ``job_type="Fulltime"``) then turn every query that loads them —
    cross-source dedup, search, stats — into a 500. This wrapper maps
    unknown stored values to a safe fallback instead of raising: the
    ``fallback`` member (e.g. ``JobType.UNKNOWN``) for non-nullable
    columns, or ``None`` for nullable ones. Raw labels are still mapped to
    enum members on bind when possible, so new writes stay canonical.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_cls, fallback=None, length: int = 50, **kwargs):
        super().__init__(length=length, **kwargs)
        self.enum_cls = enum_cls
        self.fallback = fallback

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.value
        try:
            return self.enum_cls(value).value
        except ValueError:
            return None if self.fallback is None else self.fallback.value

    def process_result_value(self, value, _dialect):
        if value is None:
            return None
        try:
            return self.enum_cls(value)
        except ValueError:
            return self.fallback


class User(Base, TimestampMixin):
    """Registered user account for personalized job alerts and matching.

    Lives in its own ``user_profiles`` table (not ``users``) to avoid
    colliding with the cybershield ``users`` table that shares the same
    database. There is no password: per the product decision, a user is
    identified by their email (login looks the profile up by email).
    ``domains`` are the alert categories the user wants (security, coding,
    data, ...); ``skills`` are the comma-separated skills they typed at
    signup (used alongside their uploaded resume for match scoring).
    """

    __tablename__ = "user_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, unique=True, index=True)
    telegram_chat_id = Column(String(100), nullable=True)
    # Phone number (E.164, e.g. +919876543210) for SMS alerts via Twilio.
    # Auto-added to live tables by init_db's ``_sync_missing_columns`` step.
    phone_number = Column(String(30), nullable=True)
    location = Column(String(100), nullable=True)
    experience_level = Column(String(50), nullable=True)  # fresher/intern/junior/senior
    domains = Column(JSON, nullable=True, default=list)
    skills = Column(JSON, nullable=True, default=list)
    is_active = Column(Boolean, default=True)
    # Secret per-user token (shown once at signup). Accounts with a token
    # require it at login; legacy accounts without one keep email-only login.
    access_token = Column(String(64), nullable=True, index=True)
    # Lowercased email of the friend who invited this user (via the
    # dashboard's invite link) — powers the referral counter.
    referred_by = Column(String(200), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<User {self.name} <{self.email}>>"


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
        LenientEnum(JobSource, fallback=JobSource.UNKNOWN, length=30),
        nullable=False,
        default=JobSource.UNKNOWN,
    )
    job_type: Column = Column(
        LenientEnum(JobType, fallback=JobType.UNKNOWN, length=30),
        nullable=False,
        default=JobType.UNKNOWN,
    )
    experience_level: Column = Column(
        LenientEnum(ExperienceLevel, fallback=None, length=30),
        nullable=True,
    )
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), nullable=True, default="USD")
    is_remote = Column(Boolean, default=False)
    posted_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=utcnow, nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True, default=list)
    # AI skill extraction: derived skills the role expects, kept separate from
    # ``tags`` so the resume matcher can compare against explicit requirements.
    # Auto-added to pre-existing tables by the startup column-sync hook.
    required_skills = Column(JSON, nullable=True, default=list)
    preferred_skills = Column(JSON, nullable=True, default=list)
    raw_data = Column(JSON, nullable=True)

    # Raw names emitted by some scrapers, mapped to canonical enum values so
    # stored sources always round-trip through the JobSource column.
    _SOURCE_ALIASES = {
        "weworkremotely": "we_work_remotely",
        "remoteok": "remote_ok",
        "hackernews_jobs": "hackernews",
        "rss": "rss_feed",
        "rss_feeds": "rss_feed",
        # Bridged cybershield sources (internship boards + vendor portals).
        "internshala": "internshala",
        "unstop": "unstop",
        "naukri": "naukri",
        "freshersworld": "freshersworld",
        "apna": "apna",
        "cutshort": "cutshort",
        "foundit": "foundit",
        "jobdexo": "jobdexo",
        "search_engine": "search_engine",
        "search": "search_engine",
        "duckduckgo": "search_engine",
        "crowdstrike": "company",
        "paloalto": "company",
        "fortinet": "company",
        "checkpoint": "company",
        "symantec": "company",
        "mcafee": "company",
        "trendmicro": "company",
    }

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

    @validates("source")
    def _coerce_job_source(self, _key: str, value):
        """Coerce any raw source string to a JobSource member.

        Guards against scrapers/API clients writing source names that are not
        defined in :class:`JobSource` — a stored value outside the enum
        crashes every read on Postgres (SQLAlchemy enum lookup), which is what
        happened live with ``weworkremotely``. Always returns a member so
        in-memory ``job.source.value`` and DB round-trips behave identically.
        """
        if value is None:
            return JobSource.UNKNOWN
        if isinstance(value, JobSource):
            return value
        raw = str(value)
        if raw in JobSource._value2member_map_:
            return JobSource._value2member_map_[raw]
        mapped = self._SOURCE_ALIASES.get(raw)
        if mapped and mapped in JobSource._value2member_map_:
            return JobSource._value2member_map_[mapped]
        return JobSource.UNKNOWN

    def __repr__(self) -> str:
        return f"<Job {self.title} at {self.company}>"


class ExpiredJob(Base, TimestampMixin):
    """Archived expired job listing.

    Jobs older than 30 days are moved here to keep the active jobs table
    lean and fast. The full job data is preserved for historical analysis.
    """

    __tablename__ = "expired_jobs"

    id = Column(String(36), primary_key=True)
    original_id = Column(String(36), index=True, nullable=False)
    title = Column(String(500), nullable=False)
    company = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(2000), nullable=True)
    source = Column(String(50), nullable=True)
    job_type = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), nullable=True)
    is_remote = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True)
    expired_at = Column(DateTime, nullable=False)
    reason = Column(String(100), nullable=True)  # expired, stale, manual
    original_created_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_expired_original", "original_id"),
        Index("idx_expired_company", "company"),
    )


class Application(Base, TimestampMixin):
    """Job application tracking model."""

    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False)
    # Optional owner of this application (multi-user); NULL keeps the legacy
    # global behavior. Added as a nullable column so the live table upgrades
    # via ``_sync_missing_columns``.
    user_id = Column(String(100), nullable=True, index=True)
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
    # How this application was created: "email" for the signed digest Apply
    # links (so the owner recap can show member activity recorded straight
    # from email), NULL for dashboard entries. Auto-added to live tables by
    # ``_sync_missing_columns``.
    source = Column(String(20), nullable=True)
    # When the "🗓️ Interview soon" reminder was last sent for this
    # application (NULL = never) so a scheduled interview is nudged at
    # most once. Auto-added to live tables by ``_sync_missing_columns``.
    interview_reminder_sent_at = Column(DateTime, nullable=True)

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
        Index("idx_application_user", "user_id"),
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


class AlertPreferences(Base, TimestampMixin):
    """Saved daily-alert preferences: which domains and channels to use.

    ``domains`` is a list of domain keys (security, coding, data, ...); an
    empty list means every domain. ``channels`` lists the delivery channels
    (email, telegram, ...); an empty list means every configured channel.
    ``min_match_score`` optionally drops jobs whose resume match % is below
    the threshold. The table is auto-created on startup by ``create_all``.
    """

    __tablename__ = "alert_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        default="user1",
    )
    domains = Column(JSON, nullable=True)
    channels = Column(JSON, nullable=True)
    min_match_score = Column(Integer, nullable=True)
    is_enabled = Column(Boolean, default=True)
    last_alert_at = Column(DateTime, nullable=True)
    # Per-time-slot categories for the three daily sends: a dict like
    # {"morning": ["security"], "afternoon": ["coding"], "evening": ["data"]}.
    # A slot not listed falls back to ``domains``.
    slot_domains = Column(JSON, nullable=True)
    # Whether the Sunday weekly digest recap is sent.
    weekly_enabled = Column(Boolean, default=True)
    # Whether a newly discovered high-match job pings the user on Telegram
    # immediately instead of waiting for the next daily slot.
    instant_alerts = Column(Boolean, default=True)
    # Whether remote / WFH / "anywhere" listings count as matching the
    # user's preferred location. On, a Bangalore user also gets fully-remote
    # security roles; off means strictly the saved city only.
    include_remote = Column(Boolean, default=True)
    # Vacation mode: when set (naive UTC), ALL alerts (daily, weekly and
    # instant) are suppressed until this timestamp. Auto-added to existing
    # live tables by init_db's ``_sync_missing_columns`` step.
    paused_until = Column(DateTime, nullable=True)
    # Job ids already flagged in a "Closing soon" alert, so each expiring
    # posting nudges the user exactly once (pruned after the job closes).
    # Auto-added to existing live tables by ``_sync_missing_columns``.
    closing_soon_sent = Column(JSON, nullable=True)
    # Whether to send the compact "📭 No new jobs today" email on days when
    # the digest found nothing new. Off means the account only ever gets
    # emails that actually contain job alerts. Auto-added to existing live
    # tables by ``_sync_missing_columns``.
    quiet_day_emails = Column(Boolean, default=True)
    # Annual minimum salary the user cares about (₹/year, INR). Jobs whose
    # listed salary is at/above this get a "💰 Meets your target" marker in
    # the digest. ``None`` = no target. Auto-added by column sync.
    min_salary = Column(Integer, nullable=True)
    # Highlight keywords: jobs whose title / description / tags / skills
    # mention any of these get a "🎯 matches …" marker in the digest.
    # Auto-added by column sync.
    keywords = Column(JSON, nullable=True)
    # Accepted experience levels (entry/junior/mid/senior/lead/executive).
    # Empty/None = every level. When set, jobs whose experience level is
    # outside the list are dropped from every alert path; listings with no
    # parsed level always stay (unspecified may still be fresher-friendly).
    # Auto-added by column sync.
    experience_levels = Column(JSON, nullable=True)

    @validates("last_alert_at", "paused_until")
    def _coerce_naive_utc(self, _key: str, value):
        """Normalize aware datetimes to naive UTC for Postgres binding."""
        return to_naive_utc(value)


class NotificationHistory(Base, TimestampMixin):
    """Record of a daily-alert digest send, for the dashboard history view.

    One row per send (manual test, one-off, or the scheduled digest) with the
    channels attempted, the categories covered, and per-channel delivery
    results. Auto-created on startup by ``create_all``.
    """

    __tablename__ = "notification_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(100),
        nullable=False,
        index=True,
        default="user1",
    )
    subject = Column(String(200), nullable=True)
    channels = Column(JSON, nullable=True)
    domains = Column(JSON, nullable=True)
    job_count = Column(Integer, default=0)
    results = Column(JSON, nullable=True)
    jobs = Column(JSON, nullable=True)
    # When the member's email client loaded the digest's tracking pixel
    # (naive UTC; NULL = never opened). Drives the owner recap's open
    # column. Auto-added to live tables by ``_sync_missing_columns``.
    opened_at = Column(DateTime, nullable=True)
    # ``jobs``: compact list of the jobs actually sent — title, company,
    # location, url, domain, match_score — so the dashboard can show
    # exactly what each digest delivered (answers "did the mail match my
    # domain/location?"). Auto-added to live tables by init_db's
    # ``_sync_missing_columns`` step.


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


class CompanyWatchlist(Base, TimestampMixin):
    """Companies a user wants to track for new job postings.

    Lives in its own ``company_watchlists`` table (not the cybershield
    ``watchlists`` table that shares the same database). One row per
    (user, company); the daily digest highlights new jobs from these
    companies even when they fall outside the user's category filter.
    """

    __tablename__ = "company_watchlists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(100), nullable=False, index=True)
    company = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("idx_cw_user_company", "user_id", "company"),)

    def __repr__(self) -> str:
        return f"<CompanyWatchlist {self.company} for {self.user_id}>"


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


class MatchSnapshot(Base, TimestampMixin):
    """A user's average resume-match % against recent jobs on one day.

    Taken daily by the scheduler, one row per ``(user_id, snapshot_date)``
    (upserted). Powers the My Matches progress chart and the weekly
    digest's trend line, so users can watch their match % improve as they
    close skill gaps.
    """

    __tablename__ = "match_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(100), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    avg_match = Column(Float, nullable=True)
    min_match = Column(Float, nullable=True)
    max_match = Column(Float, nullable=True)
    jobs_scored = Column(Integer, default=0)

    __table_args__ = (Index("idx_match_snapshot_user_day", "user_id", "snapshot_date"),)

    def __repr__(self) -> str:
        return (
            f"<MatchSnapshot {self.user_id} {self.snapshot_date} avg={self.avg_match}>"
        )
