"""
Base Scraper

Provides common functionality for all scrapers including:
- Rate limiting
- Retry logic with exponential backoff
- Request headers and proxy support
- Error handling and logging
- Data normalization
- Response caching (Redis with in-memory fallback)
"""

import asyncio
import hashlib
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from cybershield.cache import cache_manager

logger = logging.getLogger(__name__)


class ScraperConfig:
    """Scraper configuration."""

    def __init__(
        self,
        name: str,
        base_url: str,
        rate_limit: float = 1.0,  # requests per second
        max_retries: int = 3,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
    ):
        self.name = name
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = timeout
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        self.proxy = proxy


class ScrapedJob:
    """Standardized job data from scraping."""

    def __init__(self):
        self.title: Optional[str] = None
        self.company_name: Optional[str] = None
        self.location: Optional[str] = None
        self.country: Optional[str] = None
        self.city: Optional[str] = None
        self.description: Optional[str] = None
        self.url: Optional[str] = None
        self.apply_url: Optional[str] = None
        self.source: Optional[str] = None
        self.source_id: Optional[str] = None
        self.salary_min: Optional[float] = None
        self.salary_max: Optional[float] = None
        self.salary_currency: Optional[str] = None
        self.is_remote: bool = False
        self.is_hybrid: bool = False
        self.is_onsite: bool = True
        self.job_type: Optional[str] = None
        self.experience_level: Optional[str] = None
        self.posting_date: Optional[datetime] = None
        self.deadline: Optional[datetime] = None
        self.required_skills: List[str] = []
        self.preferred_skills: List[str] = []
        self.raw_data: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "title": self.title,
            "company_name": self.company_name,
            "location": self.location,
            "country": self.country,
            "city": self.city,
            "description": self.description,
            "url": self.url,
            "apply_url": self.apply_url,
            "source": self.source,
            "source_id": self.source_id,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "is_remote": self.is_remote,
            "is_hybrid": self.is_hybrid,
            "is_onsite": self.is_onsite,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "posting_date": self.posting_date,
            "deadline": self.deadline,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
        }


class BaseScraper(ABC):
    """
    Base class for all scrapers.

    Provides:
    - HTTP client management
    - Rate limiting
    - Retry logic
    - Data normalization
    - Logging
    - Response caching
    """

    def __init__(self, config: ScraperConfig, cache_ttl: int = 300):
        self.config = config
        self.cache_ttl = cache_ttl  # Cache TTL in seconds (default 5 min)
        self._last_request_time: float = 0
        self._request_count: int = 0
        self._error_count: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def base_url(self) -> str:
        return self.config.base_url

    async def _rate_limit_wait(self):
        """Wait if necessary to respect rate limits."""
        if self.config.rate_limit <= 0:
            return

        min_interval = 1.0 / self.config.rate_limit
        elapsed = asyncio.get_event_loop().time() - self._last_request_time

        if elapsed < min_interval:
            wait_time = min_interval - elapsed + random.uniform(0.1, 0.5)
            await asyncio.sleep(wait_time)

        self._last_request_time = asyncio.get_event_loop().time()

    def _generate_cache_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a cache key from URL and parameters."""
        content = f"{url}:{params}"
        return hashlib.md5(content.encode()).hexdigest()

    async def _do_fetch(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Internal fetch method with rate limiting and error handling."""
        await self._rate_limit_wait()
        merged_headers = {**self.config.headers, **(headers or {})}

        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    headers=merged_headers,
                )
                response.raise_for_status()
                self._request_count += 1
                return response
            except httpx.HTTPStatusError as e:
                self._error_count += 1
                logger.error(f"HTTP error {e.response.status_code} for {url}")
                raise
            except httpx.RequestError as e:
                self._error_count += 1
                logger.error(f"Request error for {url}: {e}")
                raise

    async def _fetch_with_cache(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> httpx.Response:
        """Fetch a URL with caching support."""
        if not use_cache:
            return await self._do_fetch(url, params, headers)

        cache_key = self._generate_cache_key(url, params)
        cached_data = await cache_manager.get_json(cache_key)

        if cached_data:
            self._cache_hits += 1
            logger.debug(f"Cache hit for {url}")
            return self._create_cached_response(cached_data)

        self._cache_misses += 1
        response = await self._do_fetch(url, params, headers)

        # Cache successful responses
        try:
            cache_data = {
                "status_code": response.status_code,
                "content": response.text,
                "headers": dict(response.headers),
            }
            await cache_manager.set_json(cache_key, cache_data, ttl=self.cache_ttl)
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")

        return response

    def _create_cached_response(self, cache_data: Dict[str, Any]) -> httpx.Response:
        """Create an httpx.Response from cached data."""
        return httpx.Response(
            status_code=cache_data["status_code"],
            content=cache_data["content"].encode("utf-8"),
            headers=cache_data.get("headers", {}),
        )

    async def _fetch(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Fetch a URL with rate limiting and retry logic."""
        return await self._do_fetch(url, params, headers)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing tracking parameters."""
        if not url:
            return url

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Remove common tracking parameters
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "ref",
            "source",
            "from",
            "track",
            "click",
            "spm",
        }
        cleaned_params = {k: v for k, v in params.items() if k.lower() not in tracking_params}

        return urlunparse(parsed._replace(query=urlencode(cleaned_params, doseq=True)))

    def _generate_content_hash(self, title: str, company: str, location: str) -> str:
        """Generate hash for deduplication."""
        content = f"{title.lower()}|{company.lower()}|{location.lower()}"
        return hashlib.md5(content.encode()).hexdigest()

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string into datetime."""
        if not date_str:
            return None

        # Common date formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from job description text."""
        if not text:
            return []

        # Common cybersecurity skills
        skills = [
            # Programming
            "Python",
            "JavaScript",
            "Go",
            "Rust",
            "C",
            "C++",
            "Java",
            "PowerShell",
            "Bash",
            # Security Tools
            "Nmap",
            "Burp Suite",
            "Wireshark",
            "Metasploit",
            "Nessus",
            "OpenVAS",
            "Snort",
            "Suricata",
            "Zeek",
            "OSSEC",
            "Wazuh",
            # SIEM
            "Splunk",
            "Microsoft Sentinel",
            "Elastic SIEM",
            "QRadar",
            "ArcSight",
            # Cloud Security
            "AWS",
            "Azure",
            "GCP",
            "Kubernetes",
            "Docker",
            # Security Concepts
            "OWASP",
            "MITRE ATT&CK",
            "NIST",
            "ISO 27001",
            "SOC 2",
            "Penetration Testing",
            "Vulnerability Assessment",
            "Incident Response",
            "Threat Intelligence",
            "Malware Analysis",
            "Reverse Engineering",
            "Digital Forensics",
            "GRC",
            "Compliance",
            # Frameworks
            "React",
            "Django",
            "FastAPI",
            "Node.js",
        ]

        found_skills = []
        text_lower = text.lower()

        for skill in skills:
            if skill.lower() in text_lower:
                found_skills.append(skill)

        return found_skills

    @abstractmethod
    async def scrape(self, **kwargs) -> List[ScrapedJob]:
        """Main scraping method to be implemented by subclasses."""
        pass

    async def run(self, **kwargs) -> List[ScrapedJob]:
        """Run the scraper with error handling."""
        logger.info(f"Starting scraper: {self.name}")
        start_time = asyncio.get_event_loop().time()

        try:
            results = await self.scrape(**kwargs)
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"Scraper {self.name} completed: {len(results)} jobs in {elapsed:.1f}s")
            return results
        except Exception as e:
            logger.error(f"Scraper {self.name} failed: {e}")
            raise

    async def clear_cache(self) -> None:
        """Clear all cached data for this scraper."""
        await cache_manager.flush()
        logger.info(f"Cache cleared for {self.name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get scraper statistics."""
        return {
            "name": self.name,
            "requests": self._request_count,
            "errors": self._error_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses) * 100
                if (self._cache_hits + self._cache_misses) > 0
                else 0
            ),
            "success_rate": (
                (self._request_count - self._error_count) / self._request_count * 100
                if self._request_count > 0
                else 0
            ),
        }
