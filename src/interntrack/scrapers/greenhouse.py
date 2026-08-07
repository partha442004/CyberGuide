"""Greenhouse job board scraper.

Many security vendors publish their careers through Greenhouse, whose public
board API (``boards-api.greenhouse.io/v1/boards/{company}/jobs``) needs no
API key, returns clean JSON, and - unlike Workday portals - does not block
server-side requests. This scraper polls a curated list of security-company
boards so the daily discovery surfaces vendor security roles directly.
"""

from typing import Any

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

# Security vendors with public Greenhouse boards (verified reachable;
# each returns 200 + a JSON job list from boards-api.greenhouse.io).
GREENHOUSE_COMPANIES = [
    "zscaler",
    "okta",
    "cloudflare",
    "knowbe4",
    "veracode",
    "beyondtrust",
    "threatlocker",
    "expel",
    "dragos",
    "tanium",
    "sumologic",
]

_BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


class GreenhouseBoardScraper(BaseScraper):
    """Fetch jobs from security-company Greenhouse career boards."""

    def __init__(self, companies: list[str] | None = None):
        super().__init__()
        self.companies = companies or GREENHOUSE_COMPANIES

    @property
    def source_name(self) -> str:
        return JobSource.COMPANY.value

    @property
    def rate_limit(self) -> int:
        return 30

    async def fetch(
        self,
        query: str,
        location: str | None = None,  # noqa: ARG002 (interface contract)
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch and filter jobs from all configured company boards."""
        jobs: list[RawJob] = []
        for company in self.companies:
            try:
                jobs.extend(await self._fetch_company(company, query, limit))
            except Exception as e:
                print(f"Error fetching Greenhouse board {company}: {e}")
                continue
        return jobs[:limit]

    async def _fetch_company(
        self,
        company: str,
        query: str,
        limit: int,
    ) -> list[RawJob]:
        response = await self._get(_BOARD_URL.format(company=company))
        response.raise_for_status()
        data = response.json()
        found: list[RawJob] = []
        for job in data.get("jobs") or []:
            title = str(job.get("title") or "").strip()
            if not title:
                continue
            # Greenhouse boards list every open role; keep only the ones the
            # discovery query actually targets (same matcher as other sources).
            if not matches_query(title, query, title=title):
                continue
            location_obj = job.get("location") or {}
            found.append(
                RawJob(
                    title=title,
                    company=str(job.get("company_name") or company.title()),
                    url=str(job.get("absolute_url") or ""),
                    description=self._clean_content(job.get("content")),
                    location=str(location_obj.get("name") or ""),
                    posted_at=self._parse_dt(job.get("first_published")),
                    expires_at=self._parse_dt(job.get("application_deadline")),
                    source=self.source_name,
                    raw_data=job,
                )
            )
            if len(found) >= limit:
                break
        return found

    @staticmethod
    def _clean_content(content: Any) -> str:
        """Strip HTML tags from the Greenhouse content blob."""
        if not content:
            return ""
        import html
        import re

        text = re.sub(r"<[^>]+>", " ", str(content))
        return html.unescape(re.sub(r"\s+", " ", text)).strip()

    @staticmethod
    def _parse_dt(value: Any):
        """Parse an ISO timestamp from the API, tolerating None/bad input."""
        if not value:
            return None
        from datetime import datetime

        from interntrack.utils.helpers import to_naive_utc

        try:
            return to_naive_utc(datetime.fromisoformat(str(value)))
        except (ValueError, TypeError):
            return None
