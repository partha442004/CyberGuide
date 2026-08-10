"""
Domain enumerations.
"""

from enum import Enum


class JobType(str, Enum):
    """Job type enumeration."""

    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class ExperienceLevel(str, Enum):
    """Experience level enumeration."""

    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class ApplicationStatus(str, Enum):
    """Application status enumeration."""

    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    REJECTED = "rejected"
    OFFER = "offer"
    JOINED = "joined"


class NotificationChannel(str, Enum):
    """Notification channel enumeration."""

    TELEGRAM = "telegram"
    EMAIL = "email"
    DISCORD = "discord"
    SLACK = "slack"
    PUSH = "push"


class ReportType(str, Enum):
    """Report type enumeration."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class JobSource(str, Enum):
    """Job source enumeration."""

    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    REMOTE_OK = "remote_ok"
    WE_WORK_REMOTELY = "we_work_remotely"
    HACKER_NEWS = "hackernews"
    RSS_FEED = "rss_feed"
    INTERNSHALA = "internshala"
    UNSTOP = "unstop"
    NAUKRI = "naukri"
    FRESHERWORLD = "freshersworld"
    APNA = "apna"
    CUTSHORT = "cutshort"
    FOUNDIT = "foundit"
    SEARCH_ENGINE = "search_engine"
    COMPANY = "company"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class SkillCategory(str, Enum):
    """Skill category enumeration."""

    PROGRAMMING = "programming"
    FRAMEWORK = "framework"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    CERTIFICATION = "certification"
    LANGUAGE = "language"
    GENERAL = "general"
