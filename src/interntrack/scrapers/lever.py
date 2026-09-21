"""Lever job board scraper.

Lever is the second-most-common no-key ATS after Greenhouse and powers the
career pages of many Indian product companies (Cred, Meesho, ...) plus
security/GRC vendors (Secureframe, ...).  Its public postings API
(``api.lever.co/v0/postings/{company}?mode=json``) returns clean JSON,
needs no API key, and does not block server-side requests — verified
reachable from datacenter IPs on 2026-09-21.

Like the Greenhouse board scraper, this polls a curated list of boards so
the daily discovery surfaces direct company roles that job-board scrapers
usually miss.
"""

from typing import Any

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

# Companies with public Lever boards (each verified returning 200 + a JSON
# posting list on 2026-09-21).  Indian product companies first (members are
# India-based), then global security/GRC vendors.
LEVER_COMPANIES = [
    # Indian product companies.
    "cred",
    "meesho",
    # Security / compliance / infrastructure vendors.
    "secureframe",
    "teleport",
    "aircall",
]

_POSTINGS_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverBoardScraper(BaseScraper):
    """Fetch jobs from curated Lever career boards."""

    def __init__(self, companies: list[str] | None = None):
        super().__init__()
        self.companies = companies or LEVER_COMPANIES

    @property
    def source_name(self) -> str:
        # Its own registry slot so it joins the "company" sweep via the
        # source list in the discovery endpoint.
        return "lever"

    @property
    def rate_limit(self) -> int:
        return 30

    async def fetch(
        self,
        query: str,
        location: str | None = None,  # noqa: ARG002 (interface contract)
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch and filter postings from all configured Lever boards.

        Boards are fetched concurrently (bounded) so the whole sweep fits
        inside the registry's per-source wall-clock cap.
        """
        import asyncio

        semaphore = asyncio.Semaphore(5)

        async def fetch_company(company: str) -> list[RawJob]:
            async with semaphore:
                try:
                    return await self._fetch_company(company, query, limit)
                except Exception as e:  # noqa: BLE001 - one bad board must not kill the sweep
                    print(f"Error fetching Lever board {company}: {e}")
                    return []

        chunks = await asyncio.gather(*(fetch_company(c) for c in self.companies))
        jobs: list[RawJob] = []
        for chunk in chunks:
            jobs.extend(chunk)
            if len(jobs) >= limit:
                break
        return jobs[:limit]

    async def _fetch_company(
        self,
        company: str,
        query: str,
        limit: int,
    ) -> list[RawJob]:
        response = await self._get(_POSTINGS_URL.format(company=company))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        found: list[RawJob] = []
        for posting in data:
            title = str(posting.get("text") or "").strip()
            if not title:
                continue
            # Lever boards list every open role; keep only the ones the
            # discovery query actually targets (same matcher as Greenhouse).
            if not matches_query(title, query, title=title):
                continue
            categories = posting.get("categories") or {}
            found.append(
                RawJob(
                    title=title,
                    company=company.title(),
                    url=str(posting.get("hostedUrl") or posting.get("applyUrl") or ""),
                    description=self._clean_content(posting.get("description")),
                    location=str(categories.get("location") or ""),
                    posted_at=self._parse_dt(posting.get("createdAt")),
                    expires_at=None,
                    source=self.source_name,
                    raw_data=posting,
                )
            )
            if len(found) >= limit:
                break
        return found

    @staticmethod
    def _clean_content(content: Any) -> str:
        """Strip HTML tags from the Lever description blob."""
        if not content:
            return ""
        import html
        import re

        text = re.sub(r"<[^>]+>", " ", str(content))
        return html.unescape(re.sub(r"\s+", " ", text)).strip()

    @staticmethod
    def _parse_dt(value: Any):
        """Lever timestamps are epoch milliseconds."""
        if not value:
            return None
        try:
            from datetime import UTC, datetime

            return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
        except (TypeError, ValueError, OSError):
            return None
