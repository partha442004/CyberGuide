"""
Wellfound (AngelList) scraper — fetches startup jobs from wellfound.com.
Uses the public search page; no API key needed.
"""

import logging
import re
from urllib.parse import urljoin

from interntrack.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)


class WellfoundScraper(BaseScraper):
    """Scrape wellfound.com (formerly AngelList) startup jobs."""

    BASE_URL = "https://wellfound.com"

    @property
    def source_name(self) -> str:
        return "wellfound"

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 50
    ) -> list[RawJob]:
        import httpx

        search_url = f"{self.BASE_URL}/role/r/{query.replace(' ', '-')}/"
        if location:
            search_url += f"in-{location.lower().replace(' ', '-')}/"

        jobs: list[RawJob] = []
        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                },
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    logger.warning(
                        "Wellfound returned %d for %s", resp.status_code, search_url
                    )
                    return jobs

                html = resp.text
                # Extract startup job cards
                card_pattern = re.compile(
                    r'<a[^>]*href="(/startup/[^"]+/jobs/[^"]+)"[^>]*>.*?</a>',
                    re.DOTALL,
                )
                cards = card_pattern.findall(html)

                for href in cards[:limit]:
                    # Extract title and company from the card URL
                    parts = href.strip("/").split("/")
                    if len(parts) >= 4:
                        company = parts[1].replace("-", " ").title()
                        title = parts[-1].replace("-", " ").title()
                    else:
                        company = "Startup"
                        title = href.split("/")[-1].replace("-", " ").title()

                    jobs.append(
                        RawJob(
                            title=title,
                            company=company,
                            url=urljoin(self.BASE_URL, href),
                            source=self.source_name,
                            description=f"{title} at {company}",
                            tags=["startup"],
                        )
                    )

        except Exception as e:
            logger.warning("Wellfound scrape failed: %s", e)

        return jobs[:limit]
