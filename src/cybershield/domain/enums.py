"""
Domain enumerations for CyberGuide.
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
    GRADUATE_PROGRAM = "graduate_program"
    WALK_IN = "walk_in"
    OFF_CAMPUS = "off_campus"
    GOVERNMENT = "government"
    UNKNOWN = "unknown"


class ExperienceLevel(str, Enum):
    """Experience level enumeration."""
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"
    INTERN = "intern"
    FRESHER = "fresher"
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
    # India
    NAUKRI = "naukri"
    FOUNDIT = "foundit"
    INTERNSHALA = "internshala"
    UNSTOP = "unstop"
    FRESHERSWORLD = "freshersworld"
    AICTE = "aicte"

    # USA
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"

    # Global
    REMOTE_OK = "remote_ok"
    HACKER_NEWS = "hackernews"
    WE_WORK_REMOTELY = "we_work_remotely"
    GOOGLE_JOBS = "google_jobs"
    RSS_FEED = "rss_feed"

    # Company Careers
    MICROSOFT = "microsoft"
    GOOGLE = "google"
    AMAZON = "amazon"
    CROWDSTRIKE = "crowdstrike"
    CLOUDFLARE = "cloudflare"
    PALO_ALTO = "palo_alto"

    # Security Platforms
    OWASP = "owasp"
    GITHUB = "github"

    # Other
    MANUAL = "manual"
    UNKNOWN = "unknown"


class SkillCategory(str, Enum):
    """Skill category enumeration."""
    PROGRAMMING = "programming"
    FRAMEWORK = "framework"
    TOOL = "tool"
    CERTIFICATION = "certification"
    SOFT_SKILL = "soft_skill"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


class SecurityDomain(str, Enum):
    """Security domain enumeration."""
    SOC = "soc"
    BLUE_TEAM = "blue_team"
    RED_TEAM = "red_team"
    PURPLE_TEAM = "purple_team"
    PENETRATION_TESTING = "penetration_testing"
    MALWARE_ANALYSIS = "malware_analysis"
    INCIDENT_RESPONSE = "incident_response"
    DIGITAL_FORENSICS = "digital_forensics"
    THREAT_INTELLIGENCE = "threat_intelligence"
    CLOUD_SECURITY = "cloud_security"
    APPLICATION_SECURITY = "application_security"
    NETWORK_SECURITY = "network_security"
    DEVSECOPS = "devsecops"
    GRC = "grc"
    IAM = "iam"
    AI_SECURITY = "ai_security"
    GENERAL = "general"


class WorkMode(str, Enum):
    """Work mode enumeration."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class RiskLevel(str, Enum):
    """Risk level for scam detection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WatchType(str, Enum):
    """Watchlist type enumeration."""
    KEYWORD = "keyword"
    COMPANY = "company"
    SKILL = "skill"


class CTFDifficulty(str, Enum):
    """CTF difficulty level."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class EventType(str, Enum):
    """Event type enumeration."""
    CONFERENCE = "conference"
    MEETUP = "meetup"
    WORKSHOP = "workshop"
    WEBINAR = "webinar"
    CTF = "ctf"
