"""
Search-engine discovery — finds job postings via DuckDuckGo HTML search.

Boards like Naukri / LinkedIn / Indeed block direct scraping from server
IPs, but their *listing URLs still show up in search results*. This scraper
queries DuckDuckGo's no-JS HTML endpoint (no API key needed), decodes the
redirect links, keeps job-board / careers-page URLs, fetches each page and
extracts title + company + description from OpenGraph/meta tags.

It's a discovery net, not a full board scraper: results are deduped against
already-saved URLs downstream, and each run is capped small so the search
engine never rate-limits us.
"""

import logging
import re
from urllib.parse import parse_qs, urlparse

from interntrack.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

# Query sent to DuckDuckGo per keyword (HTML endpoint, no key).
_SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"

# Hosts known to be job postings — a result whose URL belongs to one of
# these (or carries a job-ish path) is worth fetching.
_JOB_HOSTS = (
    "linkedin.com",
    "in.linkedin.com",
    "naukri.com",
    "indeed.com",
    "in.indeed.com",
    "glassdoor",
    "internshala.com",
    "wellfound.com",
    "timesjobs.com",
    "cutshort.io",
    "apna.co",
    "foundit.in",
    "monster.com",
    "shine.com",
    "hirect.in",
    "jobhai.com",
    "freshersworld.com",
    "unstop.com",
    "hackerearth.com",
    "lever.co",
    "greenhouse.io",
    "ashbyhq.com",
    "workable.com",
    "bamboohr.com",
    "smartrecruiters.com",
)
_JOB_PATH_MARKERS = (
    "/jobs/",
    "/job/",
    "/careers/",
    "/career/",
    "/positions",
    "/opportunities/",
    "/openings",
    "/apply/",
    "/career-page/",
)
_SKIP_HOSTS = (
    "wikipedia.org",
    "youtube.com",
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "quora.com",
    "stackoverflow.com",
    "github.com",
    "medium.com",
    "amazon.",
    "flipkart.",
)

# Salary hint inside a page title/description (INR or USD).
_SALARY_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\s*[-–]\s*[\d,]+)?)"
    r"|\$\s*([\d,]+(?:k|K)?(?:\s*[-–]\s*\$?\s*[\d,]+(?:k|K)?)?)"
)


class SearchEngineScraper(BaseScraper):
    """Discover job URLs from DuckDuckGo search results."""

    @property
    def source_name(self) -> str:
        return "search_engine"

    @property
    def rate_limit(self) -> int:
        # Aggressive: DDG rate-limits datacenter IPs quickly.
        return 20

    def _result_links(self, html: str) -> list[str]:
        """Decode DuckDuckGo result URLs from the HTML results page."""
        links: list[str] = []
        for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"', html):
            href = m.group(1)
            url = href
            # DDG wraps results in a redirect: //duckduckgo.com/l/?uddg=<enc>
            if "uddg=" in href:
                parsed = parse_qs(urlparse(href).query)
                decoded = parsed.get("uddg", [None])[0]
                if decoded:
                    url = decoded
            if url.startswith("//"):
                url = "https:" + url
            links.append(url)
        return links

    @staticmethod
    def _is_job_url(url: str) -> bool:
        """True when a search result is plausibly a job posting URL."""
        host = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        if any(skip in host for skip in _SKIP_HOSTS):
            return False
        if any(h in host for h in _JOB_HOSTS):
            return True
        return any(marker in path for marker in _JOB_PATH_MARKERS)

    def _parse_page(self, url: str, html: str) -> RawJob | None:
        """Extract title/company/description from a fetched job page."""
        title = ""
        company = ""
        description = ""
        m = re.search(r"<meta[^>]*property=\"og:title\"[^>]*content=\"([^\"]+)\"", html)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
        m = re.search(
            r"<meta[^>]*property=\"og:site_name\"[^>]*content=\"([^\"]+)\"", html
        )
        if m:
            company = m.group(1).strip()
        if not company:
            host = urlparse(url).netloc
            company = host.replace("www.", "").split(".")[0].title()
        m = re.search(
            r"<meta[^>]*(?:property=\"og:description\"|name=\"description\")"
            r"[^>]*content=\"([^\"]+)\"",
            html,
        )
        if m:
            description = m.group(1).strip()
        if not title:
            return None
        return RawJob(
            title=title[:500],
            company=company[:200],
            url=url,
            source=self.source_name,
            description=description[:2000] or None,
        )

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 8
    ) -> list[RawJob]:
        q = query.strip()
        if location:
            q = f"{q} {location}"
        # Two search flavours: targeted board search + plain query. The
        # board search finds direct listings; the plain query catches
        # career pages and smaller boards.
        queries = [
            f'"{q}" job OR vacancy OR opening',
            (
                f"{q} internship OR job site:in.linkedin.com OR site:naukri.com "
                f"OR site:internshala.com OR site:wellfound.com"
            ),
        ]
        jobs: list[RawJob] = []
        seen: set[str] = set()
        try:
            import urllib.parse

            for search in queries:
                url = _SEARCH_URL.format(query=urllib.parse.quote_plus(search))
                try:
                    resp = await self._get(url)
                except Exception as e:  # noqa: BLE001 - search must not break discovery
                    logger.warning("DDG search failed for %r: %s", q, e)
                    continue
                if resp.status_code != 200:
                    continue
                links = self._result_links(resp.text)
                kept = 0
                for link in links:
                    if not self._is_job_url(link) or link in seen:
                        continue
                    seen.add(link)
                    if len(jobs) >= limit:
                        break
                    try:
                        page = await self._get(link)
                    except Exception as e:  # noqa: BLE001
                        logger.debug("fetch %s failed: %s", link, e)
                        continue
                    if page.status_code != 200:
                        continue
                    job = self._parse_page(link, page.text)
                    if job:
                        jobs.append(job)
                        kept += 1
                if len(jobs) >= limit:
                    break
        except Exception as e:  # noqa: BLE001 - one source must not break discovery
            logger.warning("Search-engine discovery failed: %s", e)
        return jobs[:limit]
