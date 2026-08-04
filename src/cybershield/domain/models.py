"""
SQLAlchemy ORM models for CyberGuide (30+ tables).
"""

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, relationship

from cybershield.utils import utcnow


class Base(DeclarativeBase):
    """Base model for all database models."""

    pass


class TimestampMixin:
    """Mixin for timestamp fields."""

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


# ==================== CORE TABLES ====================


class User(Base, TimestampMixin):
    """User accounts and profiles."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    country = Column(String(50), default="India")
    target_role = Column(String(100), nullable=True)
    experience_level = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Company(Base, TimestampMixin):
    """Company information for tracking."""

    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), unique=True, nullable=False, index=True)
    website = Column(String(500), nullable=True)
    career_page = Column(String(500), nullable=True)
    industry = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)
    founded_year = Column(Integer, nullable=True)
    headquarters = Column(String(200), nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, default=0)
    is_watched = Column(Boolean, default=False)
    is_trusted = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True, default=list)
    social_links = Column(JSON, nullable=True)

    # Relationships
    jobs = relationship("Job", back_populates="company_ref", lazy="select")

    def __repr__(self) -> str:
        return f"<Company {self.name}>"


class Job(Base, TimestampMixin):
    """Job listing model (50+ fields)."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title = Column(String(500), nullable=False)
    company = Column(String(200), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    department = Column(String(100), nullable=True)
    job_id_external = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(2000), nullable=False, unique=True)
    apply_url = Column(String(2000), nullable=True)
    source = Column(String(50), nullable=False, index=True)
    source_url = Column(String(2000), nullable=True)
    job_type = Column(String(50), nullable=False, index=True)
    experience_level = Column(String(50), nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), default="INR")
    location = Column(String(200), nullable=True)
    country = Column(String(50), nullable=True, index=True)
    city = Column(String(100), nullable=True)
    is_remote = Column(Boolean, default=False)
    work_mode = Column(String(20), nullable=True)
    duration = Column(String(50), nullable=True)
    deadline = Column(DateTime, nullable=True)
    openings = Column(Integer, nullable=True)
    eligibility = Column(JSON, nullable=True)
    degree = Column(String(100), nullable=True)
    branch = Column(String(100), nullable=True)
    cgpa_min = Column(Float, nullable=True)
    batch = Column(String(50), nullable=True)
    required_skills = Column(JSON, default=list)
    preferred_skills = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    benefits = Column(JSON, nullable=True)
    selection_process = Column(Text, nullable=True)
    interview_process = Column(Text, nullable=True)
    hr_email = Column(String(255), nullable=True)
    recruiter_name = Column(String(200), nullable=True)
    recruiter_linkedin = Column(String(500), nullable=True)
    hiring_manager = Column(String(200), nullable=True)
    company_size = Column(String(50), nullable=True)
    industry = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    posted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, nullable=True)
    raw_data = Column(JSON, nullable=True)

    # Relationships
    company_ref = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job", lazy="selectin")
    skills = relationship("JobSkill", back_populates="job", lazy="selectin")
    scam_score = relationship("ScamScore", back_populates="job", uselist=False, lazy="selectin")

    __table_args__ = (
        Index("idx_job_posted", "posted_at"),
        Index("idx_job_deadline", "deadline"),
    )

    def __repr__(self) -> str:
        return f"<Job {self.title} at {self.company}>"


class Skill(Base, TimestampMixin):
    """Skills database for matching and recommendations."""

    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    difficulty_level = Column(Integer, default=1)
    demand_score = Column(Float, default=0)
    trend_score = Column(Float, default=0)
    learning_resources = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)

    # Relationships
    user_skills = relationship("UserSkill", back_populates="skill")
    job_skills = relationship("JobSkill", back_populates="skill")

    def __repr__(self) -> str:
        return f"<Skill {self.name}>"


class Application(Base, TimestampMixin):
    """Application tracking with Kanban pipeline."""

    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="saved")
    applied_at = Column(DateTime, nullable=True)
    interview_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    resume_version = Column(String(100), nullable=True)
    cover_letter = Column(Text, nullable=True)
    priority = Column(Integer, default=0)
    reminded = Column(Boolean, default=False)
    resume_match_score = Column(Float, nullable=True)
    ats_score = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", backref="applications")
    job = relationship("Job", back_populates="applications")
    status_history = relationship(
        "ApplicationStatusHistory",
        back_populates="application",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_application_user", "user_id"),
        Index("idx_application_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Application {self.status} for {self.job_id}>"


# ==================== TRACKING TABLES ====================


class Watchlist(Base, TimestampMixin):
    """Keyword and company watchlists."""

    __tablename__ = "watchlists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    watch_type = Column(String(50), nullable=False)
    value = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    notification_channels = Column(JSON, default=["telegram"])
    match_count = Column(Integer, default=0)
    last_matched = Column(DateTime, nullable=True)

    __table_args__ = (Index("idx_watchlist_type_value", "watch_type", "value"),)

    def __repr__(self) -> str:
        return f"<Watchlist {self.watch_type}: {self.value}>"


class Bookmark(Base, TimestampMixin):
    """User bookmarks for jobs, companies, etc."""

    __tablename__ = "bookmarks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type = Column(String(50), nullable=False)
    item_id = Column(String(36), nullable=False)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list)

    def __repr__(self) -> str:
        return f"<Bookmark {self.item_type}:{self.item_id}>"


class ResumeData(Base, TimestampMixin):
    """User resume information."""

    __tablename__ = "resume_data"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    file_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=False)
    skills = Column(JSON, default=list)
    education = Column(JSON, default=list)
    experience = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    certifications = Column(JSON, default=list)
    github_url = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    parsed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ResumeData {self.id}>"


# ==================== AI ENGINE TABLES ====================


class ScamScore(Base, TimestampMixin):
    """AI-generated scam analysis results."""

    __tablename__ = "scam_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    scam_score = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    flags = Column(JSON, default=list)
    reasons = Column(JSON, default=list)
    is_scam = Column(Boolean, default=False)
    analyzed_at = Column(DateTime, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="scam_score")

    def __repr__(self) -> str:
        return f"<ScamScore {self.scam_score} for job {self.job_id}>"


class Prediction(Base, TimestampMixin):
    """AI prediction results."""

    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_type = Column(String(50), nullable=False)
    target_entity = Column(String(100), nullable=True)
    prediction = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=False)
    valid_until = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Prediction {self.prediction_type}>"


class SalaryEstimate(Base, TimestampMixin):
    """AI-estimated salary data."""

    __tablename__ = "salary_estimates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    estimated_min = Column(Integer, nullable=False)
    estimated_max = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False)
    confidence = Column(Float, nullable=False)
    city_comparison = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<SalaryEstimate {self.estimated_min}-{self.estimated_max}>"


class SkillTrend(Base, TimestampMixin):
    """Skill market trend data."""

    __tablename__ = "skill_trends"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id = Column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period = Column(String(20), nullable=False)
    period_start = Column(DateTime, nullable=False)
    demand_count = Column(Integer, default=0)
    growth_rate = Column(Float, default=0)
    avg_salary = Column(Float, nullable=True)
    top_companies = Column(JSON, default=list)

    def __repr__(self) -> str:
        return f"<SkillTrend {self.skill_id}>"


# ==================== EVENT TABLES ====================


class CTFEvent(Base, TimestampMixin):
    """CTF competition tracking."""

    __tablename__ = "ctf_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=True)
    url = Column(String(500), nullable=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    registration_url = Column(String(500), nullable=True)
    prize = Column(Text, nullable=True)
    difficulty = Column(String(20), nullable=True)
    format = Column(String(50), nullable=True)
    is_registered = Column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<CTFEvent {self.name}>"


class BugBountyProgram(Base, TimestampMixin):
    """Bug bounty program tracking."""

    __tablename__ = "bug_bounty_programs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company = Column(String(200), nullable=False)
    platform = Column(String(100), nullable=True)
    url = Column(String(500), nullable=False)
    scope = Column(Text, nullable=True)
    rewards = Column(JSON, nullable=True)
    min_bounty = Column(Integer, nullable=True)
    max_bounty = Column(Integer, nullable=True)
    status = Column(String(20), default="active")
    is_new = Column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<BugBountyProgram {self.company}>"


class Event(Base, TimestampMixin):
    """Conferences, meetups, workshops."""

    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    event_type = Column(String(50), nullable=False)
    organizer = Column(String(200), nullable=True)
    url = Column(String(500), nullable=False)
    location = Column(String(200), nullable=True)
    is_virtual = Column(Boolean, default=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    registration_url = Column(String(500), nullable=True)
    price = Column(Float, nullable=True)
    is_free = Column(Boolean, default=False)
    topics = Column(JSON, default=list)

    def __repr__(self) -> str:
        return f"<Event {self.name}>"


class Certification(Base, TimestampMixin):
    """Certification tracking."""

    __tablename__ = "certifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    provider = Column(String(100), nullable=False)
    url = Column(String(500), nullable=True)
    exam_fee = Column(Float, nullable=True)
    voucher_available = Column(Boolean, default=False)
    voucher_deadline = Column(DateTime, nullable=True)
    student_discount = Column(Boolean, default=False)
    validity_years = Column(Integer, nullable=True)
    difficulty = Column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<Certification {self.name}>"


# ==================== RELATIONSHIP TABLES ====================


class JobSkill(Base):
    """Many-to-many relationship between jobs and skills."""

    __tablename__ = "job_skills"

    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    importance = Column(Integer, default=1)
    is_required = Column(Boolean, default=True)

    # Relationships
    job = relationship("Job", back_populates="skills")
    skill = relationship("Skill", back_populates="job_skills")


class UserSkill(Base, TimestampMixin):
    """User skill proficiency tracking."""

    __tablename__ = "user_skills"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    proficiency_level = Column(Integer, default=1)
    last_used = Column(DateTime, nullable=True)
    is_learning = Column(Boolean, default=False)

    # Relationships
    skill = relationship("Skill", back_populates="user_skills")


class ApplicationStatusHistory(Base, TimestampMixin):
    """Application status change history."""

    __tablename__ = "application_status_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id = Column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_at = Column(DateTime, default=utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="status_history")


class DuplicateGroup(Base, TimestampMixin):
    """Deduplication tracking."""

    __tablename__ = "duplicate_groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    canonical_job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    duplicate_job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    match_type = Column(String(50), nullable=False)


# ==================== ANALYTICS TABLES ====================


class NewsAnalysis(Base, TimestampMixin):
    """Cybersecurity news analysis."""

    __tablename__ = "news_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title = Column(String(500), nullable=False)
    source = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    published_at = Column(DateTime, nullable=True)
    category = Column(String(50), nullable=True)
    companies_mentioned = Column(JSON, default=list)
    hiring_impact = Column(Float, nullable=True)
    analysis = Column(Text, nullable=True)


class InterviewPrep(Base, TimestampMixin):
    """Interview preparation data."""

    __tablename__ = "interview_prep"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    role = Column(String(200), nullable=False)
    technical_questions = Column(JSON, default=list)
    hr_questions = Column(JSON, default=list)
    scenario_questions = Column(JSON, default=list)
    company_specific = Column(JSON, default=list)


class ResumeMatchResult(Base, TimestampMixin):
    """Resume-job match analysis results."""

    __tablename__ = "resume_match_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resume_id = Column(String(36), ForeignKey("resume_data.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    match_score = Column(Float, nullable=False)
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    ats_score = Column(Float, nullable=True)
    suggestions = Column(JSON, default=list)


class AnalyticsSnapshot(Base, TimestampMixin):
    """Analytics data snapshots."""

    __tablename__ = "analytics_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_type = Column(String(50), nullable=False)
    period = Column(DateTime, nullable=False)
    data = Column(JSON, nullable=False)


class NotificationConfig(Base, TimestampMixin):
    """User notification preferences."""

    __tablename__ = "notification_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50), nullable=False)
    is_enabled = Column(Boolean, default=True)
    config = Column(JSON, default=dict)
    last_notified = Column(DateTime, nullable=True)


class ActivityLog(Base, TimestampMixin):
    """User activity tracking."""

    __tablename__ = "activity_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)


class ScheduledReport(Base, TimestampMixin):
    """Report scheduling configuration."""

    __tablename__ = "scheduled_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String(50), nullable=False)
    frequency = Column(String(50), nullable=False)
    is_enabled = Column(Boolean, default=True)
    last_generated = Column(DateTime, nullable=True)
    next_generation = Column(DateTime, nullable=True)
    recipients = Column(JSON, default=list)


class GeneratedReport(Base, TimestampMixin):
    """Report generation history."""

    __tablename__ = "generated_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    report_type = Column(String(50), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    data = Column(JSON, nullable=False)
    file_path = Column(String(500), nullable=True)
    sent_via = Column(JSON, default=list)
