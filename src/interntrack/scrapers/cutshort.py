"""
Direct Cutshort.io scraper — fetches from cutshort.io/jobs search page.

No API key needed; parses the server-rendered search HTML. Cutshort is a
React/Next.js app but still renders job cards into the initial HTML, and
each card's title link carries the direct posting URL
(``https://cutshort.io/job/{Title}-{Location}-{Company}-{code}``). The
company and location live *inside the slug* (title words are stripped and
the trailing token is the job code), so this scraper reconstructs them
from the slug instead of relying on markup class names that change between
deploys.

The relevance filter mirrors Cutshort's own client-side keyword behaviour
(any query word in the title keeps the card) and the whole run is bounded
(12s timeouts) so serverless discovery never hangs.
"""

import logging
import re
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, _stem

logger = logging.getLogger(__name__)

# Card anchor: <a href="https://cutshort.io/job/<slug>" ...><div ...>title</div></a>
# The anchor carries extra attributes (target/class) after href, and the
# title div may carry its own attributes — match both tolerantly.
_CARD_ANCHOR = re.compile(
    r'<a[^>]*href="(https://cutshort\.io/job/[^"]+)"[^>]*>'
    r"\s*<div[^>]*>\s*([^<]+?)\s*</div>\s*</a>",
    re.DOTALL,
)

# City tokens that appear inside Cutshort job slugs ("Bengaluru-Bangalore-",
# "Remote", "Mumbai") and must be stripped when recovering the company name.
_LOCATION_TOKENS = frozenset(
    {
        "bangalore",
        "bengaluru",
        "bengalore",
        "mumbai",
        "bombay",
        "chennai",
        "delhi",
        "ncr",
        "noida",
        "gurgaon",
        "gurugram",
        "pune",
        "hyderabad",
        "secunderabad",
        "kolkata",
        "kerala",
        "kochi",
        "coimbatore",
        "ahmedabad",
        "jaipur",
        "remote",
        "india",
        "in",
        "work-from-home",
        "wfh",
        "hybrid",
        "onsite",
    }
)


class CutshortScraper(BaseScraper):
    """Scrape cutshort.io public job listings."""

    BASE_URL = "https://cutshort.io"

    @property
    def source_name(self) -> str:
        return "cutshort"

    @property
    def rate_limit(self) -> int:
        return 15

    def _search_url(self, query: str, location: str | None = None) -> str:
        """Search URL — cutshort filters by query + optional city.

        Cutshort's server page always renders a fixed popular-jobs list and
        applies the query filter client-side after load, so the URL is only
        cosmetic for a raw-HTML fetch — the relevance filter below decides
        what actually counts as a match (mirroring the site's own keyword
        behaviour: any query word in the title keeps the card).
        """
        params = {"query": query}
        if location:
            # Cutshort knows the big metros by their common names.
            city = location.strip().lower()
            for name in (
                "bangalore",
                "mumbai",
                "chennai",
                "delhi",
                "pune",
                "hyderabad",
            ):
                if name in city:
                    params["city"] = name
                    break
        return f"{self.BASE_URL}/jobs?{urlencode(params)}"

    @staticmethod
    def _company_from_slug(slug: str, title: str) -> str:
        """Recover the company name embedded in a Cutshort job slug.

        Slug shape: ``{Title}-{Location?}-{Company}-{code}`` — e.g.
        ``Sr-Engineering-Manager-Egnyte-koBBDTQ1`` or
        ``Senior-Software-Architect-Bengaluru-Bangalore-NeoGenCode-
        Technologies-Pvt-Ltd-EMFogiZR``. Title words and location tokens are
        stripped (case-insensitively) first, so the job code is guaranteed
        to be the *last remaining token* — dropping it unconditionally
        (codes may or may not contain digits) leaves the company.
        """
        parts = slug.split("-")
        title_words = {w.lower() for w in re.findall(r"[a-z0-9]+", title.lower())}
        kept = []
        for part in parts:
            low = part.lower()
            if low in title_words or low in _LOCATION_TOKENS:
                continue
            kept.append(part)
        if kept:
            kept.pop()  # trailing job code
        return " ".join(kept).strip() or "Unknown"

    @staticmethod
    def _card_matches(title: str, query: str) -> bool:
        """Whether a Cutshort card matches the discovery query.

        Cutshort's own client filter keeps any job whose title contains a
        query keyword, so the strict AND matcher (used by the board
        scrapers) would reject every popular-list card for a two-word query
        like "software engineer". Mirror the site: any significant query
        word appearing in the title keeps the card. Niche queries that
        match nothing on the popular list simply yield zero jobs — the
        search-engine discovery path still surfaces genuine filtered
        Cutshort postings through its ``site:cutshort.io`` query.
        """
        tokens = [_stem(t) for t in _stem(query.lower()).split() if len(t) >= 3]
        title_stemmed = _stem(title.lower())
        return any(
            re.search(rf"\b{re.escape(token)}\b", title_stemmed) for token in tokens
        )

    def _extract_cards(self, html: str) -> list[dict]:
        """Parse job cards into {title, company, url, location} dicts."""
        out: list[dict] = []
        seen: set[str] = set()
        for m in _CARD_ANCHOR.finditer(html):
            url = m.group(1).strip()
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            if not title or url in seen:
                continue
            seen.add(url)
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            out.append(
                {
                    "title": title,
                    "company": self._company_from_slug(slug, title),
                    "url": url,
                }
            )
        return out

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 25
    ) -> list[RawJob]:
        """Fetch jobs from Cutshort."""
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
                logger.warning("Cutshort returned %d for %s", resp.status_code, url)
                return []

            cards = self._extract_cards(resp.text)
            for card in cards[:limit]:
                if not self._card_matches(card["title"], query):
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
            logger.warning("Cutshort scrape failed: %s", e)

        return jobs[:limit]
