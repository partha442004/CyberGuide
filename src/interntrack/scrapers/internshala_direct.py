"""
Direct Internshala scraper — fetches from internshala.com/internships.
No API key needed; parses the public HTML listing page.

Internshala serves its keyword/city search paths (``/internships/keyword/...``,
``/internships/{city}/{query}/``) by *redirecting to the generic internships
page*, which is why older builds saved the "all internships" URL instead of a
direct posting. The stable per-category page
``https://internshala.com/internships/{query}-internship/`` is used instead:
it returns real filtered cards whose ``individual_internship`` divs carry the
direct detail link in the ``data-href`` attribute
(``/internship/detail/{slug}{id}``).
"""

import logging
import re
from urllib.parse import urljoin, urlparse

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class InternshalaDirectScraper(BaseScraper):
    """Scrape internshala.com public internship listings."""

    BASE_URL = "https://internshala.com"

    # The card div's opening tag carries the direct detail URL in data-href
    # (e.g. /internship/detail/cyber-security-internship-in-...1785990156).
    # Internshala emits it single-quoted (data-href='/internship/detail/...'),
    # so both quote styles are accepted.
    _CARD_OPEN = re.compile(
        r'<div[^>]*class="[^"]*individual_internship[^"]*"[^>]*>', re.DOTALL
    )
    _DATA_HREF = re.compile(r"data-href=['\"]([^'\"]+)['\"]")
    _TITLE = re.compile(
        r'<a[^>]*class="job-title-href"[^>]*>\s*([^<]+?)\s*</a>', re.DOTALL
    )
    _COMPANY = re.compile(
        r'class="(?:company-name|company_name)"[^>]*>\s*([^<]+?)\s*<', re.DOTALL
    )
    # Any anchor to a direct posting (fallback when the card regex misses).
    _DETAIL_ANCHOR = re.compile(
        r'<a[^>]*class="job-title-href"[^>]*href="(/internship/detail/[^"]+)"[^>]*>'
        r"\s*([^<]+?)\s*</a>",
        re.DOTALL,
    )

    @property
    def source_name(self) -> str:
        return "internshala"

    def _search_url(self, query: str, location: str | None = None) -> str:
        """Category page URL — the only format that does not redirect."""
        slug = query.strip().lower().replace(" ", "-")
        base = f"{self.BASE_URL}/internships/{slug}-internship/"
        if location:
            city = location.strip().lower().replace(" ", "-")
            # City-suffixed category pages exist for the big metros
            # (e.g. ...-internship-in-bangalore/).
            return f"{self.BASE_URL}/internships/{slug}-internship-in-{city}/"
        return base

    def _extract_cards(self, html: str) -> list[dict]:
        """Parse posting cards into {title, company, url} dicts.

        Only direct ``/internship/detail/...`` links are kept — a listing
        whose detail link can't be found is skipped (never a search page).
        """
        out: list[dict] = []
        seen: set[str] = set()
        for m in self._CARD_OPEN.finditer(html):
            open_tag = m.group(0)
            data_href = self._DATA_HREF.search(open_tag)
            url = data_href.group(1) if data_href else None
            if not url or "/internship/detail/" not in url:
                continue
            window = html[m.end() : m.end() + 3000]
            title_m = self._TITLE.search(window)
            title = title_m.group(1).strip() if title_m else ""
            if not title:
                continue
            company_m = self._COMPANY.search(window)
            company = company_m.group(1).strip() if company_m else "Unknown"
            full = urljoin(self.BASE_URL, url)
            if full in seen:
                continue
            seen.add(full)
            out.append({"title": title, "company": company, "url": full})
        return out

    def _extract_detail_anchors(self, html: str) -> list[dict]:
        """Fallback extraction straight from title anchors."""
        out: list[dict] = []
        seen: set[str] = set()
        for href, title in self._DETAIL_ANCHOR.findall(html):
            title = title.strip()
            if not title:
                continue
            full = urljoin(self.BASE_URL, href)
            if full in seen:
                continue
            seen.add(full)
            out.append({"title": title, "company": "Unknown", "url": full})
        return out

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 50
    ) -> list[RawJob]:
        import httpx

        # City-suffixed category pages only exist for the big metros; when a
        # city page yields nothing (or the metro slug doesn't exist) fall back
        # to the plain category page — the digests filter by user location
        # downstream anyway.
        candidates = [self._search_url(query, location)]
        if location:
            candidates.append(self._search_url(query, None))
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
                cards: list[dict] = []
                for search_url in candidates:
                    resp = await client.get(search_url)
                    if resp.status_code != 200:
                        logger.warning(
                            "Internshala returned %d for %s",
                            resp.status_code,
                            search_url,
                        )
                        continue

                    html = resp.text
                    # Internshala canonicalizes slugs server-side (e.g.
                    # ``cybersecurity-internship`` -> ``cyber-security-internship``),
                    # so the final URL is trusted. Only an unknown slug redirects
                    # to the bare /internships/ page — then retry with the keyword
                    # search page and let the relevance filter drop the junk.
                    final_path = urlparse(str(resp.url)).path.rstrip("/")
                    if final_path in ("/internships", ""):
                        q_url = (
                            f"{self.BASE_URL}/internships/?q="
                            + query.strip().replace(" ", "+")
                        )
                        resp = await client.get(q_url)
                        if resp.status_code != 200:
                            continue
                        html = resp.text

                    cards = self._extract_cards(html)
                    if not cards:
                        cards = self._extract_detail_anchors(html)
                    # The generic feed only appears for unknown slugs / cities;
                    # keep entries that actually match the query (same precision
                    # helper the other board scrapers use) and only stop once a
                    # candidate yields relevant cards.
                    cards = [
                        card
                        for card in cards
                        if matches_query(card["title"], query, title=card["title"])
                    ]
                    if cards:
                        break
                for card in cards[:limit]:
                    jobs.append(
                        RawJob(
                            title=card["title"],
                            company=card["company"],
                            url=card["url"],
                            source=self.source_name,
                            description=None,
                        )
                    )
        except Exception as e:  # noqa: BLE001 - one source must not break discovery
            logger.warning("Internshala scrape failed: %s", e)

        return jobs[:limit]
