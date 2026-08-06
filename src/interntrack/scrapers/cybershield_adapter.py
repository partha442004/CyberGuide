"""Adapter bridging cybershield scrapers into the interntrack discovery pipeline.

The live discovery registry (``interntrack.scrapers.registry``) only knew
about the five original sources (HackerNews, RSS feeds, LinkedIn, Indeed,
Glassdoor). The project also ships a much richer scraper library under
``cybershield.scrapers`` - Indian internship boards (Internshala, Unstop,
Naukri, Freshersworld) and direct security-company career portals (CrowdStrike,
Palo Alto, Fortinet, Check Point, ...) - that was never wired into the
deployed pipeline.

This adapter wraps a cybershield scraper behind the interntrack
:class:`~interntrack.scrapers.base.BaseScraper` interface (``fetch() ->
list[RawJob]``) so those sources participate in the same discovery, dedup,
matching and alerting flow as everything else.
"""

import asyncio
from typing import Any

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

# Blocked / slow sources fail fast instead of stalling the whole discovery
# run (Vercel serverless functions have a hard timeout).
_SOURCE_TIMEOUT = 8.0


class CybershieldScraperAdapter(BaseScraper):
    """Adapt a cybershield scraper to the interntrack scraper interface."""

    def __init__(self, source_name: str, cybershield_scraper: Any):
        super().__init__()
        self._source_name = source_name
        self._cyber = cybershield_scraper

    @property
    def source_name(self) -> str:
        return self._source_name

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        """Run the wrapped cybershield scraper and map results to RawJob."""
        # Build scrape kwargs
        scrape_kwargs: dict[str, Any] = {"keywords": [query], "max_pages": 2}
        if location:
            scrape_kwargs["location"] = location

        try:
            scraped = await asyncio.wait_for(
                self._cyber.scrape(**scrape_kwargs),
                timeout=_SOURCE_TIMEOUT,
            )
        except TimeoutError:
            return []
        except TypeError:
            # Some cybershield scrapers accept only **kwargs.
            try:
                scraped = await asyncio.wait_for(
                    self._cyber.scrape(keywords=[query]),
                    timeout=_SOURCE_TIMEOUT,
                )
            except TimeoutError:
                return []

        jobs: list[RawJob] = []
        for item in scraped or []:
            raw = item.to_dict()
            title = str(raw.get("title") or "").strip()
            if not title:
                continue
            if not matches_query(title, query, title=title):
                continue
            jobs.append(
                RawJob(
                    title=title,
                    company=str(raw.get("company_name") or "Unknown"),
                    url=str(raw.get("apply_url") or raw.get("url") or ""),
                    description=str(raw.get("description") or ""),
                    location=str(raw.get("location") or ""),
                    salary_min=raw.get("salary_min"),
                    salary_max=raw.get("salary_max"),
                    salary_currency=str(raw.get("salary_currency") or "INR"),
                    job_type=str(raw.get("job_type") or ""),
                    is_remote=bool(raw.get("is_remote")),
                    posted_at=raw.get("posting_date") or raw.get("created_at"),
                    expires_at=raw.get("deadline"),
                    tags=list(raw.get("required_skills") or [])
                    + list(raw.get("preferred_skills") or []),
                    source=self._source_name,
                    raw_data=raw,
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
