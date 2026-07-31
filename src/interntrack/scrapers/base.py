"""
Base scraper class for job discovery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    description: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    job_type: Optional[str] = None
    is_remote: bool = False
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    source: str = "unknown"
    raw_data: Optional[Dict[str, Any]] = None

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
    def rate_limit(self) -> int:
        """Rate limit in requests per minute."""
        return 60

    @abstractmethod
    async def fetch(
        self,
        query: str,
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
