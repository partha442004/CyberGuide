"""
Base scraper class for job discovery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from interntrack.config import get_settings

settings = get_settings()


@dataclass
class RawJob:
    """Raw job data from scraper."""

    title: str
    company: str
    url: str
    description: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    job_type: str | None = None
    is_remote: bool = False
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    source: str = "unknown"
    raw_data: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "description": self.description,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "job_type": self.job_type,
            "is_remote": self.is_remote,
            "posted_at": self.posted_at,
            "expires_at": self.expires_at,
            "tags": self.tags,
            "source": self.source,
            "raw_data": self.raw_data,
        }


# Security-family keywords used to expand a security-focused discovery query
# so that e.g. "cybersecurity" also surfaces SOC / pentest / appsec listings
# that never use the literal word "cybersecurity".
SECURITY_KEYWORDS = (
    "security",
    "cybersecurity",
    "infosec",
    "information security",
    "soc",
    "penetration",
    "pentest",
    "vapt",
    "ethical hacking",
    "threat",
    "vulnerability",
    "incident response",
    "forensics",
    "malware",
    "cryptography",
    "zero trust",
    "firewall",
    "intrusion",
    "red team",
    "blue team",
    "appsec",
    "devsecops",
    "siem",
)

# Queries containing any of these tokens trigger the security-family expansion.
_SECURITY_TRIGGERS = frozenset(
    {"cybersecurity", "security", "infosec", "vapt", "pentest", "penetration"},
)


def matches_query(text: str, query: str) -> bool:
    """Return True when ``text`` matches the discovery ``query``.

    Matching is deliberately broad for discovery:
    - multi-word queries match when ANY token appears (a "security analyst"
      search also surfaces "Security Engineer" listings);
    - security-family queries are expanded with related security keywords so
      a "cybersecurity" search also catches SOC, pentest, appsec roles;
    - short tokens (< 3 chars) are ignored.
    """
    text_lower = text.lower()
    tokens = [
        token for token in query.lower().replace(",", " ").split() if len(token) >= 3
    ]
    if not tokens:
        return True

    keywords = set(tokens)
    if keywords & _SECURITY_TRIGGERS:
        keywords.update(SECURITY_KEYWORDS)

    return any(keyword in text_lower for keyword in keywords)


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

    @property
    def rate_limit(self) -> int:
        """Rate limit in requests per minute."""
        return 60

    @abstractmethod
    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch jobs from the source."""

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
