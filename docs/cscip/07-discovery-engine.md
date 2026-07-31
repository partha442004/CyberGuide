# CyberShield Career Intelligence Platform (CSCIP) - Discovery Engine

## Overview

The Discovery Engine is the core of CSCIP, responsible for automated job discovery from 40+ sources across India and USA. It uses a plugin-based architecture with intelligent scraping, deduplication, and verification.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DISCOVERY ENGINE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SCRAPER REGISTRY                                  │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │   India     │  │    USA      │  │   Global    │                │   │
│  │  │  Scrapers   │  │  Scrapers   │  │  Scrapers   │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │  Company    │  │  Security   │  │    CTF      │                │   │
│  │  │  Careers    │  │  Platforms  │  │  Platforms  │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │    Bug      │  │  Learning   │  │    News     │                │   │
│  │  │   Bounty    │  │  Platforms  │  │   Sources   │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PROCESSING PIPELINE                               │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │  │  Fetch   │───▶│  Parse   │───▶│  Dedup   │───▶│  Verify  │     │   │
│  │  │  Jobs    │    │  Data    │    │  Jobs    │    │  Jobs    │     │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │  │  Scam    │───▶│Classify  │───▶│  Score   │───▶│  Store   │     │   │
│  │  │  Detect  │    │  Jobs    │    │  Jobs    │    │  DB      │     │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST-PROCESSING                                   │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │  │Watchlist │    │ Notify   │    │Analytics │    │  Cache   │     │   │
│  │  │  Check   │    │  Users   │    │ Update   │    │ Update   │     │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Source Registry (40+ Sources)

### India Sources

| Source | Scraper | Rate Limit | Method |
|--------|---------|------------|--------|
| Naukri | `naukri.py` | 15 req/min | HTML parsing |
| Foundit (Monster) | `foundit.py` | 15 req/min | HTML parsing |
| Internshala | `internshala.py` | 20 req/min | API + HTML |
| Unstop | `unstop.py` | 20 req/min | API |
| Freshersworld | `freshersworld.py` | 15 req/min | HTML parsing |
| AICTE Portal | `aicte.py` | 10 req/min | HTML parsing |
| Government (CERT-In, CDAC, NIC, DRDO, ISRO, BEL, BHEL) | `government.py` | 5 req/min | HTML parsing |

### USA Sources

| Source | Scraper | Rate Limit | Method |
|--------|---------|------------|--------|
| LinkedIn | `linkedin.py` | 10 req/min | HTML parsing |
| Indeed | `indeed.py` | 15 req/min | HTML parsing |
| Glassdoor | `glassdoor.py` | 10 req/min | HTML parsing |

### Company Career Pages (20+)

| Company | Scraper | Career Page |
|---------|---------|-------------|
| Microsoft | `microsoft.py` | careers.microsoft.com |
| Google | `google.py` | careers.google.com |
| Amazon | `amazon.py` | amazon.jobs |
| Cisco | `cisco.py` | jobs.cisco.com |
| IBM | `ibm.py` | ibm.com/careers |
| Oracle | `oracle.py` | oracle.com/careers |
| CrowdStrike | `crowdstrike.py` | crowdstrike.com/careers |
| Palo Alto | `palo_alto.py` | paloaltonetworks.com/careers |
| Fortinet | `fortinet.py` | fortinet.com/careers |
| Check Point | `checkpoint.py` | checkpoint.com/careers |
| Rapid7 | `rapid7.py` | rapid7.com/careers |
| Qualys | `qualys.py` | qualys.com/careers |
| Tenable | `tenable.py` | tenable.com/careers |
| Cloudflare | `cloudflare.py` | cloudflare.com/careers |
| Zscaler | `zscaler.py` | zscaler.com/careers |
| Datadog | `datadog.py` | datadog.com/careers |
| Elastic | `elastic.py` | elastic.co/careers |
| Splunk | `splunk.py` | splunk.com/careers |
| OpenAI | `openai.py` | openai.com/careers |
| Anthropic | `anthropic.py` | anthropic.com/careers |

### Global Sources

| Source | Scraper | Rate Limit | Method |
|--------|---------|------------|--------|
| RemoteOK | `remoteok.py` | 30 req/min | JSON API |
| HackerNews | `hackernews.py` | 30 req/min | Firebase API |
| We Work Remotely | `we_work_remotely.py` | 30 req/min | HTML parsing |
| Google Jobs | `google_jobs.py` | 10 req/min | HTML parsing |
| RSS Feeds | `rss_feeds.py` | 60 req/min | feedparser |

### Security Platforms

| Source | Scraper | Purpose |
|--------|---------|---------|
| OWASP | `owasp.py` | Security jobs, events |
| GitHub | `github.py` | Security repos, jobs |
| GitLab | `gitlab.py` | Security projects |

### CTF Platforms

| Source | Scraper | Purpose |
|--------|---------|---------|
| CTFtime | `ctftime.py` | CTF competitions |
| HackTheBox | `hackthebox.py` | CTFs, jobs |

### Bug Bounty Platforms

| Source | Scraper | Purpose |
|--------|---------|---------|
| HackerOne | `hackerone.py` | Bug bounty programs |
| Bugcrowd | `bugcrowd.py` | Bug bounty programs |
| Intigriti | `intigriti.py` | Bug bounty programs |

### Learning Platforms

| Source | Scraper | Purpose |
|--------|---------|---------|
| TryHackMe | `tryhackme.py` | Learning paths |
| HackTheBox | `hackthebox.py` | Challenges |
| PortSwigger | `portswigger.py` | Web security |
| PicoCTF | `picoctf.py` | CTF learning |
| OverTheWire | `overthewire.py` | Wargames |

### News Sources

| Source | Scraper | Purpose |
|--------|---------|---------|
| BleepingComputer | `bleeping_computer.py` | Security news |
| The Hacker News | `the_hacker_news.py` | Security news |
| SecurityWeek | `security_week.py` | Security news |

---

## Search Keywords

### Primary Keywords
```
Cyber Security, Cybersecurity, Information Security
SOC Analyst, SOC Engineer, SOC Intern
Security Analyst, Security Engineer
Threat Intelligence, Threat Hunting
Detection Engineering
Blue Team, Red Team, Purple Team
Ethical Hacking, Penetration Testing
VAPT (Vulnerability Assessment & Penetration Testing)
Application Security, AppSec
DevSecOps
Cloud Security, AWS Security, Azure Security, GCP Security
IAM (Identity and Access Management)
Identity Security
Network Security
Linux Security, Windows Security
SIEM (Security Information and Event Management)
Splunk, Microsoft Sentinel, Elastic Security, QRadar
Malware Analysis, Reverse Engineering
Digital Forensics, Incident Response (DFIR)
Security Research
GRC (Governance, Risk, Compliance)
Compliance
OT Security, ICS Security
AI Security, LLM Security
Container Security, Kubernetes Security
API Security
Zero Trust
```

### Secondary Keywords
```
Pen Tester, Security Consultant
Bug Bounty Hunter
Security Auditor
Risk Analyst
Compliance Officer
Security Architect
CISO, CSO
Security Manager
Incident Handler
Forensic Analyst
Malware Researcher
Vulnerability Analyst
Security Operations
SOC L1, SOC L2, SOC L3
```

---

## Data Collection Fields

### Core Fields (Always Collected)

| Field | Type | Description |
|-------|------|-------------|
| company | string | Company name |
| role | string | Job title/role |
| department | string | Department |
| job_id_external | string | External job ID |
| posting_date | datetime | When posted |
| deadline | datetime | Application deadline |
| experience | string | Experience required |
| salary_min | integer | Minimum salary/stipend |
| salary_max | integer | Maximum salary/stipend |
| currency | string | Currency code |
| location | string | Full location |
| country | string | Country |
| city | string | City |
| remote | boolean | Remote available |
| work_mode | enum | remote, hybrid, onsite |
| duration | string | Internship duration |
| required_skills | array | Required skills |
| preferred_skills | array | Preferred skills |
| description | text | Full description |
| application_link | string | Apply URL |
| official_career_link | string | Official career page |
| source_url | string | Source website |

### Extended Fields (When Available)

| Field | Type | Description |
|-------|------|-------------|
| hr_email | string | HR contact email |
| recruiter_name | string | Recruiter name |
| recruiter_linkedin | string | Recruiter LinkedIn |
| hiring_manager | string | Hiring manager |
| benefits | array | Job benefits |
| selection_process | text | Selection process |
| interview_process | text | Interview process |
| company_size | string | Company size |
| industry | string | Industry |
| openings | integer | Number of openings |
| eligibility | object | Eligibility criteria |
| degree | string | Required degree |
| branch | string | Required branch |
| cgpa_min | float | Minimum CGPA |
| batch | string | Target batch |

---

## Scraper Base Class

```python
# src/cybershield/scrapers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from cybershield.config import get_settings

settings = get_settings()


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


@dataclass
class RawJob:
    """Raw job data from scraper."""
    
    title: str
    company: str
    url: str
    description: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    is_remote: bool = False
    work_mode: Optional[WorkMode] = None
    duration: Optional[str] = None
    deadline: Optional[datetime] = None
    openings: Optional[int] = None
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    eligibility: Optional[Dict[str, Any]] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    cgpa_min: Optional[float] = None
    batch: Optional[str] = None
    hr_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_linkedin: Optional[str] = None
    hiring_manager: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    apply_url: Optional[str] = None
    source: str = "unknown"
    source_url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    posted_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "description": self.description,
            "location": self.location,
            "country": self.country,
            "city": self.city,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "is_remote": self.is_remote,
            "work_mode": self.work_mode.value if self.work_mode else None,
            "duration": self.duration,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "openings": self.openings,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "benefits": self.benefits,
            "eligibility": self.eligibility,
            "degree": self.degree,
            "branch": self.branch,
            "cgpa_min": self.cgpa_min,
            "batch": self.batch,
            "hr_email": self.hr_email,
            "recruiter_name": self.recruiter_name,
            "recruiter_linkedin": self.recruiter_linkedin,
            "hiring_manager": self.hiring_manager,
            "company_size": self.company_size,
            "industry": self.industry,
            "apply_url": self.apply_url,
            "source": self.source,
            "source_url": self.source_url,
            "raw_data": self.raw_data,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


class BaseScraper(ABC):
    """Base class for all job scrapers."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the job source."""
        pass
    
    @property
    @abstractmethod
    def source_url(self) -> str:
        """Base URL of the source."""
        pass
    
    @property
    def rate_limit(self) -> int:
        """Rate limit in requests per minute."""
        return 30
    
    @property
    def supported_countries(self) -> List[str]:
        """Countries supported by this scraper."""
        return ["global"]
    
    @abstractmethod
    async def fetch(
        self,
        query: str,
        country: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 100,
    ) -> List[RawJob]:
        """Fetch jobs from the source."""
        pass
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _get(self, url: str, **kwargs) -> httpx.Response:
        """Make HTTP GET request with retry."""
        return await self.client.get(url, **kwargs)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _post(self, url: str, **kwargs) -> httpx.Response:
        """Make HTTP POST request with retry."""
        return await self.client.post(url, **kwargs)
```

---

## Scraper Registry

```python
# src/cybershield/scrapers/registry.py

from typing import Dict, List, Optional

from cybershield.scrapers.base import BaseScraper


class ScraperRegistry:
    """Registry for managing scraper instances."""
    
    def __init__(self):
        self._scrapers: Dict[str, BaseScraper] = {}
    
    def register(self, scraper: BaseScraper) -> None:
        """Register a scraper."""
        self._scrapers[scraper.source_name] = scraper
    
    def unregister(self, source_name: str) -> None:
        """Unregister a scraper."""
        if source_name in self._scrapers:
            del self._scrapers[source_name]
    
    def get(self, source_name: str) -> Optional[BaseScraper]:
        """Get a scraper by source name."""
        return self._scrapers.get(source_name)
    
    def get_all(self) -> List[BaseScraper]:
        """Get all registered scrapers."""
        return list(self._scrapers.values())
    
    def get_by_country(self, country: str) -> List[BaseScraper]:
        """Get scrapers supporting a specific country."""
        return [
            s for s in self._scrapers.values()
            if country in s.supported_countries or "global" in s.supported_countries
        ]
    
    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self._scrapers.keys())
    
    async def fetch_all(
        self,
        query: str,
        country: Optional[str] = None,
        sources: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[dict]:
        """Fetch jobs from all or specified sources."""
        all_jobs = []
        scrapers = self.get_all()
        
        if sources:
            scrapers = [s for s in scrapers if s.source_name in sources]
        
        if country:
            scrapers = [s for s in scrapers if country in s.supported_countries or "global" in s.supported_countries]
        
        for scraper in scrapers:
            try:
                jobs = await scraper.fetch(query, country=country, limit=limit)
                all_jobs.extend([job.to_dict() for job in jobs])
            except Exception as e:
                print(f"Error fetching from {scraper.source_name}: {e}")
                continue
        
        return all_jobs
    
    async def close_all(self) -> None:
        """Close all scraper clients."""
        for scraper in self.get_all():
            await scraper.close()


def get_default_registry() -> ScraperRegistry:
    """Create default scraper registry with all scrapers."""
    registry = ScraperRegistry()
    
    # India scrapers
    from cybershield.scrapers.india.naukri import NaukriScraper
    from cybershield.scrapers.india.internshala import InternshalaScraper
    from cybershield.scrapers.india.unstop import UnstopScraper
    from cybershield.scrapers.india.freshersworld import FreshersworldScraper
    
    registry.register(NaukriScraper())
    registry.register(InternshalaScraper())
    registry.register(UnstopScraper())
    registry.register(FreshersworldScraper())
    
    # USA scrapers
    from cybershield.scrapers.usa.linkedin import LinkedInScraper
    from cybershield.scrapers.usa.indeed import IndeedScraper
    
    registry.register(LinkedInScraper())
    registry.register(IndeedScraper())
    
    # Global scrapers
    from cybershield.scrapers.global.remoteok import RemoteOKScraper
    from cybershield.scrapers.global.hackernews import HackerNewsScraper
    from cybershield.scrapers.global.rss_feeds import RSSFeedScraper
    
    registry.register(RemoteOKScraper())
    registry.register(HackerNewsScraper())
    registry.register(RSSFeedScraper())
    
    # Company career scrapers
    from cybershield.scrapers.company_careers.crowdstrike import CrowdStrikeScraper
    from cybershield.scrapers.company_careers.cloudflare import CloudflareScraper
    
    registry.register(CrowdStrikeScraper())
    registry.register(CloudflareScraper())
    
    # Security platform scrapers
    from cybershield.scrapers.security_platforms.owasp import OWASPScraper
    
    registry.register(OWASPScraper())
    
    return registry
```

---

## Discovery Pipeline

```python
# src/cybershield/services/discovery_service.py

from typing import List, Optional
from datetime import datetime, timezone

from cybershield.scrapers.registry import ScraperRegistry, get_default_registry
from cybershield.engines.deduplication import DeduplicationEngine
from cybershield.engines.verification import VerificationEngine
from cybershield.engines.scam_detection import ScamDetectionEngine
from cybershield.engines.classification import ClassificationEngine
from cybershield.services.job_service import JobService
from cybershield.services.notification_service import NotificationManager
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)


class DiscoveryService:
    """Service for orchestrating job discovery."""
    
    def __init__(self, session):
        self.session = session
        self.registry = get_default_registry()
        self.dedup_engine = DeduplicationEngine(session)
        self.verification_engine = VerificationEngine(session)
        self.scam_engine = ScamDetectionEngine(session)
        self.classification_engine = ClassificationEngine(session)
        self.job_service = JobService(session)
        self.notification_manager = NotificationManager(session)
    
    async def run_discovery(
        self,
        query: str = "cybersecurity",
        country: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> dict:
        """Run complete discovery pipeline."""
        logger.info(f"Starting discovery: query={query}, country={country}")
        
        # Step 1: Fetch jobs from all sources
        raw_jobs = await self.registry.fetch_all(
            query=query,
            country=country,
            sources=sources,
        )
        logger.info(f"Fetched {len(raw_jobs)} raw jobs")
        
        # Step 2: Deduplication
        unique_jobs = await self.dedup_engine.filter_unique(raw_jobs)
        logger.info(f"After dedup: {len(unique_jobs)} unique jobs")
        
        # Step 3: Verification
        verified_jobs = []
        for job in unique_jobs:
            is_valid, issues = await self.verification_engine.verify_job(job)
            if is_valid:
                verified_jobs.append(job)
            else:
                logger.debug(f"Job failed verification: {job.get('title')} - {issues}")
        logger.info(f"After verification: {len(verified_jobs)} valid jobs")
        
        # Step 4: Scam Detection
        safe_jobs = []
        for job in verified_jobs:
            scam_result = await self.scam_engine.analyze_job(job)
            if not scam_result.get("is_scam", False):
                job["scam_score"] = scam_result.get("scam_score", 0)
                safe_jobs.append(job)
            else:
                logger.warning(f"Scam detected: {job.get('title')} - Score: {scam_result.get('scam_score')}")
        logger.info(f"After scam detection: {len(safe_jobs)} safe jobs")
        
        # Step 5: Classification
        classified_jobs = []
        for job in safe_jobs:
            classification = await self.classification_engine.classify_job(job)
            job.update(classification)
            classified_jobs.append(job)
        
        # Step 6: Save to database
        saved_count = 0
        for job in classified_jobs:
            try:
                await self.job_service.create_job(job)
                saved_count += 1
            except Exception as e:
                logger.debug(f"Failed to save job: {e}")
                continue
        
        # Step 7: Check watchlists and notify
        await self._check_watchlists(classified_jobs)
        
        result = {
            "discovered": len(raw_jobs),
            "unique": len(unique_jobs),
            "verified": len(verified_jobs),
            "safe": len(safe_jobs),
            "saved": saved_count,
            "scam_detected": len(verified_jobs) - len(safe_jobs),
        }
        
        logger.info(f"Discovery complete: {result}")
        return result
    
    async def _check_watchlists(self, jobs: List[dict]):
        """Check jobs against user watchlists and send notifications."""
        from cybershield.repositories.watchlist_repository import WatchlistRepository
        
        watchlist_repo = WatchlistRepository(self.session)
        watchlists = await watchlist_repo.get_active_watchlists()
        
        for job in jobs:
            for watchlist in watchlists:
                if self._matches_watchlist(job, watchlist):
                    await self.notification_manager.notify_watchlist_match(
                        watchlist=watchlist,
                        job=job,
                    )
    
    def _matches_watchlist(self, job: dict, watchlist) -> bool:
        """Check if job matches a watchlist entry."""
        if watchlist.watch_type == "keyword":
            return watchlist.value.lower() in (
                f"{job.get('title', '')} {job.get('description', '')}".lower()
            )
        elif watchlist.watch_type == "company":
            return watchlist.value.lower() == job.get("company", "").lower()
        elif watchlist.watch_type == "skill":
            return watchlist.value.lower() in [
                s.lower() for s in job.get("required_skills", [])
            ]
        return False
```

---

## Keyword Management

### Cybersecurity Keywords Configuration

```python
# src/cybershield/config/keywords.py

CYBERSECURITY_KEYWORDS = {
    # Primary roles
    "primary": [
        "cyber security",
        "cybersecurity",
        "information security",
        "infosec",
        "soc analyst",
        "soc engineer",
        "soc intern",
        "security analyst",
        "security engineer",
        "security intern",
    ],
    
    # Specialized roles
    "specialized": [
        "threat intelligence",
        "threat hunting",
        "detection engineering",
        "blue team",
        "red team",
        "purple team",
        "ethical hacking",
        "penetration testing",
        "vapt",
        "application security",
        "appsec",
        "devsecops",
    ],
    
    # Cloud security
    "cloud": [
        "cloud security",
        "aws security",
        "azure security",
        "gcp security",
        "iam",
        "identity security",
    ],
    
    # Infrastructure security
    "infrastructure": [
        "network security",
        "linux security",
        "windows security",
        "siem",
        "splunk",
        "microsoft sentinel",
        "elastic security",
        "qradar",
    ],
    
    # Analysis roles
    "analysis": [
        "malware analysis",
        "reverse engineering",
        "digital forensics",
        "incident response",
        "dfir",
        "security research",
    ],
    
    # Governance
    "governance": [
        "grc",
        "compliance",
        "ot security",
        "ics security",
    ],
    
    # Emerging
    "emerging": [
        "ai security",
        "llm security",
        "container security",
        "kubernetes security",
        "api security",
        "zero trust",
    ],
}


def get_all_keywords() -> List[str]:
    """Get all keywords as a flat list."""
    keywords = []
    for category in CYBERSECURITY_KEYWORDS.values():
        keywords.extend(category)
    return keywords


def get_keywords_by_category(category: str) -> List[str]:
    """Get keywords for a specific category."""
    return CYBERSECURITY_KEYWORDS.get(category, [])
```

---

## Rate Limiting

```python
# src/cybershield/utils/rate_limiter.py

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict


class RateLimiter:
    """Async rate limiter for scrapers."""
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def acquire(self, source: str, rate_limit: int) -> bool:
        """Acquire rate limit slot."""
        async with self._locks[source]:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)
            
            # Remove old requests
            self._requests[source] = [
                req_time for req_time in self._requests[source]
                if req_time > cutoff
            ]
            
            # Check if under limit
            if len(self._requests[source]) < rate_limit:
                self._requests[source].append(now)
                return True
            
            return False
    
    async def wait_for_slot(self, source: str, rate_limit: int):
        """Wait until a rate limit slot is available."""
        while not await self.acquire(source, rate_limit):
            await asyncio.sleep(1)
```

---

**Module Status**: ✅ Complete

**Next Module**: [Module 8: Verification Engine](./08-verification-engine.md)
