"""
Direct JobDexo scraper — fetches from jobdexo.com search pages.

JobDexo bills itself as "India's first job index for freshers": it
aggregates off-campus / fresher roles (Fulltime, Internship, WFH, Remote)
with direct posting URLs, company, location, salary band, job-type badge
and a deadline — all server-rendered, no API key needed. The search form is
a plain ``GET /?q=<query>`` and each result card's title link is the direct
posting URL (``/job/{code}/{slug}``), so saved jobs never point at a search
page. The digest / dashboard filter by user city downstream, so the search
page itself only needs the keyword query.
"""

import html
import logging
import re
from datetime import datetime
from urllib.parse import urlencode, urljoin

import httpx

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


def _unescape(text: str) -> str:
    """Decode HTML entities, including double-escaped ones.

    JobDexo sometimes double-escapes card titles (&amp;amp;), so a single
    ``html.unescape`` pass is not enough — loop until the text stabilises.
    """
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


# One server-rendered card per listing. The card block carries everything
# the digest needs: title link (direct posting), company, meta items
# (location, salary), the Fulltime/Internship badge and the deadline.
_CARD = re.compile(r'<article class="job-card">(.*?)</article>', re.DOTALL)
_TITLE_ANCHOR = re.compile(
    r'<h3 class="job-title">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_COMPANY = re.compile(r'class="job-company">\s*([^<]+?)\s*<', re.DOTALL)
# Meta items are ``<span class="job-meta-item"><svg>…</svg>text</span>``.
_META_ITEM = re.compile(
    r'<span class="job-meta-item">\s*<svg.*?</svg>\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
_BADGE = re.compile(r'class="job-badge[^"]*">\s*([^<]+?)\s*<', re.DOTALL)
_DEADLINE = re.compile(
    r'class="job-deadline[^"]*">\s*[⏳\s]*Deadline:\s*([^<]+?)\s*<',
    re.DOTALL,
)
# The short teaser paragraph under the meta row.
_DESC = re.compile(r'<p style="font-size:\.85rem[^>]*>(.*?)</p>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

_INTERNSHIP_TOKENS = ("intern", "trainee", "apprenticeship")
_REMOTE_TOKENS = ("remote", "work from home", "work-from-home", "wfh", "anywhere")


class JobDexoScraper(BaseScraper):
    """Scrape jobdexo.com public fresher/off-campus job listings."""

    BASE_URL = "https://jobdexo.com"

    @property
    def source_name(self) -> str:
        return "jobdexo"

    @property
    def rate_limit(self) -> int:
        return 30

    def _search_url(self, query: str, _location: str | None = None) -> str:
        """Search URL — the site's only filter is the keyword query.

        The ``type`` shortcut mirrors the homepage filters (``/?type=wfh``,
        ``/?type=remote``, ``/?type=internship``) so internship and remote
        searches land on the right tab instead of the fulltime list. City
        filtering is not a URL parameter on JobDexo; the digest applies the
        user's location downstream.
        """
        params: dict[str, str] = {"q": query}
        q = query.lower()
        if any(tok in q for tok in _INTERNSHIP_TOKENS):
            params["type"] = "internship"
        elif any(tok in q for tok in _REMOTE_TOKENS):
            params["type"] = "remote"
        return f"{self.BASE_URL}/?{urlencode(params)}"

    @staticmethod
    def _parse_salary(text: str) -> tuple[int | None, int | None]:
        """Parse an INR salary band from JobDexo meta text.

        Handles the two formats JobDexo emits: lakh-per-annum bands
        ("3.5 LPA", "3 - 5 LPA") and rupee ranges ("₹ 6,500 - 10,000").
        Returns ``(min, max)`` or ``(None, None)``.
        """
        text = text.strip()
        lpa = re.search(r"([\d.]+)\s*-\s*([\d.]+)\s*LPA", text, re.IGNORECASE)
        if lpa:
            lo = int(float(lpa.group(1)) * 100_000)
            hi = int(float(lpa.group(2)) * 100_000)
            return (lo, hi)
        single_lpa = re.search(r"([\d.]+)\s*LPA", text, re.IGNORECASE)
        if single_lpa:
            val = int(float(single_lpa.group(1)) * 100_000)
            return (val, val)
        rng = re.search(r"₹\s*([\d,]+)\s*[-–]\s*₹?\s*([\d,]+)", text)
        if rng:
            return (
                int(rng.group(1).replace(",", "")),
                int(rng.group(2).replace(",", "")),
            )
        single = re.search(r"₹\s*([\d,]+)", text)
        if single:
            val = int(single.group(1).replace(",", ""))
            return (val, val)
        return (None, None)

    @staticmethod
    def _parse_deadline(text: str) -> datetime | None:
        """Parse a "31 Dec 2026" deadline into a naive-UTC datetime."""
        from datetime import UTC

        from interntrack.utils.helpers import to_naive_utc

        text = re.sub(r"\s+", " ", text).strip()
        try:
            parsed = datetime.strptime(text, "%d %b %Y").replace(tzinfo=UTC)
            return to_naive_utc(parsed)
        except ValueError:
            return None

    def _extract_cards(self, html_text: str) -> list[dict]:
        """Parse listing cards into {title, company, url, ...} dicts."""
        out: list[dict] = []
        seen: set[str] = set()
        for m in _CARD.finditer(html_text):
            card = m.group(1)
            title_m = _TITLE_ANCHOR.search(card)
            if not title_m:
                continue
            href, title = title_m.group(1), _unescape(title_m.group(2)).strip()
            if not title:
                continue
            full = urljoin(self.BASE_URL, href)
            if full in seen:
                continue
            seen.add(full)
            company_m = _COMPANY.search(card)
            meta = [_unescape(t.strip()) for t in _META_ITEM.findall(card)]
            badge_m = _BADGE.search(card)
            deadline_m = _DEADLINE.search(card)
            desc_m = _DESC.search(card)
            desc = ""
            if desc_m:
                desc = re.sub(r"\s+", " ", _TAG_RE.sub("", desc_m.group(1))).strip()
            out.append(
                {
                    "title": title,
                    "company": (
                        _unescape(company_m.group(1)).strip()
                        if company_m
                        else "Unknown"
                    ),
                    "url": full,
                    "location": meta[0] if meta else None,
                    "salary_text": meta[1] if len(meta) > 1 else "",
                    "job_type": badge_m.group(1).strip() if badge_m else None,
                    "deadline": (
                        self._parse_deadline(deadline_m.group(1))
                        if deadline_m
                        else None
                    ),
                    "description": desc or None,
                }
            )
        return out

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 50,
    ) -> list[RawJob]:
        """Fetch and filter JobDexo search results for the query."""
        jobs: list[RawJob] = []
        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                },
            ) as client:
                resp = await client.get(self._search_url(query, location))
                if resp.status_code != 200:
                    logger.warning(
                        "JobDexo returned %d for %s",
                        resp.status_code,
                        self._search_url(query, location),
                    )
                    return jobs
                cards = self._extract_cards(resp.text)
                for card in cards:
                    if len(jobs) >= limit:
                        break
                    if not matches_query(card["title"], query, title=card["title"]):
                        continue
                    meta_text = " ".join(
                        filter(None, [card["location"], card["salary_text"]])
                    ).lower()
                    is_remote = any(tok in meta_text for tok in _REMOTE_TOKENS)
                    salary_min, salary_max = self._parse_salary(card["salary_text"])
                    jobs.append(
                        RawJob(
                            title=card["title"],
                            company=card["company"],
                            url=card["url"],
                            description=card["description"],
                            location=card["location"],
                            salary_min=salary_min,
                            salary_max=salary_max,
                            salary_currency="INR" if salary_min else "USD",
                            job_type=card["job_type"],
                            is_remote=is_remote,
                            expires_at=card["deadline"],
                            source=self.source_name,
                            tags=["fresher", "off-campus"],
                        )
                    )
        except Exception as e:  # noqa: BLE001 - one source must not break discovery
            logger.warning("JobDexo scrape failed: %s", e)

        return jobs[:limit]
