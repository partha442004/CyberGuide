"""
Direct Foundit.in (Monster India) scraper.

Foundit blocks datacenter IPs with HTTP 403, so from serverless hosts this
scraper usually returns zero jobs — that is fine and by design: the
search-engine discovery scraper surfaces ``foundit.in/job/...`` posting
URLs through its Bing fallback (Foundit is already in the engine's allowed
hosts), so Foundit listings still reach the pipeline. When this scraper
*does* get through (residential IP, VPN, changed bot policy), it parses the
public search page the same way the other board scrapers do.

No API key needed; gracefully degrades on 403/404/timeout and never raises.
"""

import logging
import re
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)

# Foundit posting URLs: /job/{title}-{company}-{city}-{id}
_JOB_LINK = re.compile(r'href="(/job/[a-z0-9-]+)"', re.IGNORECASE)
_TITLE = re.compile(
    r'<a[^>]*href="(/job/[a-z0-9-]+)"[^>]*>([^<]{4,120}?)</a>', re.IGNORECASE
)


class FounditScraper(BaseScraper):
    """Scrape foundit.in public job search pages (best effort)."""

    BASE_URL = "https://www.foundit.in"

    @property
    def source_name(self) -> str:
        return "foundit"

    @property
    def rate_limit(self) -> int:
        return 15

    def _search_url(self, query: str, location: str | None = None) -> str:
        params = {"query": query}
        if location:
            params["locations"] = location.strip()
        return f"{self.BASE_URL}/search/?{urlencode(params)}"

    def _extract_cards(self, html: str) -> list[dict]:
        """Parse job links into {title, company, url} dicts."""
        out: list[dict] = []
        seen: set[str] = set()
        # Prefer anchored titles (title text next to the link).
        for m in _TITLE.finditer(html):
            url = f"{self.BASE_URL}{m.group(1)}"
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            if not title or url in seen:
                continue
            seen.add(url)
            out.append({"title": title, "company": "Unknown", "url": url})
        if out:
            return out
        # Fallback: bare links, title inferred from the slug.
        for m in _JOB_LINK.finditer(html):
            url = f"{self.BASE_URL}{m.group(1)}"
            if url in seen:
                continue
            seen.add(url)
            slug = m.group(1).rsplit("/", 1)[-1]
            words = slug.split("-")
            # Drop the trailing numeric id + city-ish tokens to guess a title.
            while words and (words[-1].isdigit() or len(words[-1]) < 4):
                words.pop()
            title = " ".join(words).strip() or "Foundit job"
            out.append({"title": title, "company": "Unknown", "url": url})
        return out

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 25
    ) -> list[RawJob]:
        """Fetch jobs from Foundit (may return [] when bot-gated)."""
        jobs: list[RawJob] = []
        try:
            url = self._search_url(query, location)
            resp = await self._get(
                url,
                timeout=12,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-IN,en;q=0.9",
                },
            )
            if resp.status_code != 200:
                logger.debug(
                    "Foundit %s for %s (bot-gated from this host?) — "
                    "search-engine discovery covers it via Bing",
                    resp.status_code,
                    url,
                )
                return []

            cards = self._extract_cards(resp.text)
            for card in cards[:limit]:
                if not matches_query(card["title"], query, title=card["title"]):
                    continue
                jobs.append(
                    RawJob(
                        title=card["title"],
                        company=card["company"],
                        url=card["url"],
                        source=self.source_name,
                        location=location or "India",
                        tags=[],
                    )
                )
        except Exception as e:  # noqa: BLE001 - one source must not break discovery
            logger.debug("Foundit scrape failed: %s", e)

        return jobs[:limit]
