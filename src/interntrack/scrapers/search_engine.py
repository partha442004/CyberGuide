"""
Search-engine discovery — finds job postings via DuckDuckGo HTML search.

Boards like Naukri / LinkedIn / Indeed block direct scraping from server
IPs, but their *posting URLs still show up in search results*. This scraper
queries DuckDuckGo's no-JS HTML endpoint (no API key needed), decodes the
redirect links, keeps URLs that look like individual postings (not board
search/listing pages), fetches each page and extracts title + company +
description from OpenGraph/meta tags.

It's a discovery net, not a full board scraper: results are deduped against
already-saved URLs downstream, and each run is capped small so the search
engine never rate-limits us.
"""

import base64
import logging
import re
from urllib.parse import parse_qs, parse_qsl, urlparse

from interntrack.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

# Query sent to DuckDuckGo per keyword (HTML endpoint, no key).
_SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"

# Bing fallback (HTML, no key) — DDG blocks some datacenter IPs, Bing
# tolerates them and can be pinned to the Indian market.
_BING_URL = "https://www.bing.com/search?mkt=en-IN&setlang=en&q={query}"

# Hosts known to carry job postings — a result whose URL belongs to one of
# these is worth fetching *unless* it is a board listing/search page.
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

# URL shapes that mean "this is a search / listing page, not a posting".
# E.g. linkedin.com/jobs/cyber-security-intern-jobs-bengaluru,
# naukri.com/...-jobs-in-bangalore, indeed /q-cyber-security...jobs.html,
# glassdoor ...-jobs-SRCH_..., internshala /internships/...-internship/.
# Note: bare /jobs/ is NOT a listing marker because some boards post under
# it (wellfound.com/jobs/4562736-slug) — listing shapes are matched by
# their more specific forms instead.
_LISTING_MARKERS = (
    "-jobs",
    "jobs-in-",
    "vacancies-in-",
    "/job-search",
    "/jobsearch",
    "/jobs/q-",
    "/jobs/all/",
    "/jobs/search",
    "/search",
    "/results",
    "/browse",
    "/q-",
    "SRCH_",
    "jobsearch",
    "?q=",
    "&q=",
    "/internships/",
    "/posts/",
    "/registration/",
    "/startups/l/",
    "/role/l/",
    "/companies/",
    "/salary/",
    "/blog/",
    "/article/",
    "/alternative/",
    "/hc/",
)

# URL shapes that are (almost) always individual postings.
_POSTING_MARKERS = (
    "viewjob",
    "vjk=",
    "/jobs/view/",
    "/job-listings",
    "/job-listing",
    "/job-details/",
    "/internship/detail/",
    "/job/",
    "/position/",
    "/positions",
    "/requisition",
    "/jobid=",
    "jobId=",
    "/career-page/",
    "/openings/",
    "/opportunities/",
    "/apply/",
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
    # Docs / help / marketing / app subdomains, not postings.
    "help.",
    "support.",
    "recruiter.",
    "reach.",
    "app.",
    "hire.",
    "learn.",
    "developers.",
    "developer.",
    "career.wellfound.com",
)

# Titles that are search pages, e.g. "SOC Analyst jobs | Dice.com",
# "384 Results for Soc Analyst Jobs", "Job Search | Naukri",
# "Jobs in Bangalore: ... Vacancies in August | Internshala".
_LISTING_TITLE_RE = re.compile(
    r"^\d+\s+(results?|jobs?|internships?|vacancies?)\s+for\b"
    r"|\b(job search|search jobs|find jobs)\b"
    r"|\b(jobs?|internships?|vacancies|openings)\b.*\|\s*[a-z0-9.\-]+\s*$",
    re.IGNORECASE,
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
    def _decode_bing_redirect(url: str) -> str:
        """Decode a bing.com/ck/a redirect back to the real result URL."""
        if "bing.com/ck/a" not in url:
            return url
        params = dict(parse_qsl(urlparse(url).query))
        encoded = params.get("u", "")
        if not encoded:
            return url
        # Bing base64-encodes the target with a leading "a1" marker.
        payload = encoded[2:] if encoded.startswith("a1") else encoded
        padded = payload + "=" * (-len(payload) % 4)
        try:
            return base64.urlsafe_b64decode(padded).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001 - never break discovery on one link
            return url

    @classmethod
    def _bing_links(cls, html: str) -> list[str]:
        """Extract + decode Bing organic result URLs."""
        links: list[str] = []
        for m in re.finditer(r'<h2[^>]*><a[^>]*href="([^"]+)"', html):
            href = m.group(1).replace("&amp;", "&")
            url = cls._decode_bing_redirect(href)
            if url.startswith("//"):
                url = "https:" + url
            links.append(url)
        return links

    async def _search_links(self, engine: str, query: str) -> list[str]:
        """Return decoded result URLs from one search engine."""
        import urllib.parse

        if engine == "bing":
            url = _BING_URL.format(query=urllib.parse.quote_plus(query))
            resp = await self._get(url, timeout=12)
            return self._bing_links(resp.text)
        url = _SEARCH_URL.format(query=urllib.parse.quote_plus(query))
        resp = await self._get(url, timeout=12)
        return self._result_links(resp.text)

    @staticmethod
    def _is_job_url(url: str) -> bool:
        """True when a search result is plausibly an individual posting.

        Board search pages (linkedin ``/jobs/<title>-jobs-<city>``, naukri
        ``...-jobs-in-<city>``, indeed ``/q-...jobs.html``, glassdoor
        ``/Job/...SRCH_...``, internshala ``/internships/...``) are
        rejected — they are listings, not postings, and their pages have
        no single job title to save. Listing shapes always win, even when
        the URL also looks posting-ish (glassdoor ``/Job/`` paths).
        """
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        full = url.lower()
        if any(skip in host for skip in _SKIP_HOSTS):
            return False
        if any(marker in full for marker in _LISTING_MARKERS):
            return False
        # A bare host root (jobs.lever.co/, app landing, board homepage) is
        # never an individual posting.
        if path in ("", "/", "/index.html", "/index.htm"):
            return False
        if any(h in host for h in _JOB_HOSTS):
            return True
        return any(marker in path for marker in _POSTING_MARKERS)

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
        if not title or _LISTING_TITLE_RE.search(title):
            return None
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
        # Unquoted queries: DDG's HTML endpoint silently returns nothing for
        # heavily-qualified strings, so keep each flavour short. The plain
        # queries catch postings on smaller boards (infosec-career.com etc)
        # and career pages; per-site queries surface postings on boards
        # whose listing pages dominate the generic results (cutshort,
        # wellfound, foundit/timesjobs/hirect).
        queries = [
            f"{q} job OR vacancy OR opening",
            f"{q} internship OR fresher OR career",
            f"site:cutshort.io {q}",
            f"site:wellfound.com {q}",
            f"site:foundit.in OR site:timesjobs.com OR site:hirect.in {q}",
        ]
        jobs: list[RawJob] = []
        seen: set[str] = set()
        try:
            for search in queries:
                # DuckDuckGo first; Bing covers the datacenter-IP cases
                # where DDG serves an anomaly page with no result links.
                links: list[str] = []
                for engine in ("duckduckgo", "bing"):
                    try:
                        found = await self._search_links(engine, search)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("%s search failed for %r: %s", engine, q, e)
                        continue
                    links.extend(found)
                    if any(self._is_job_url(link) for link in found):
                        break
                for link in links:
                    if not self._is_job_url(link) or link in seen:
                        continue
                    seen.add(link)
                    if len(jobs) >= limit:
                        break
                    try:
                        page = await self._get(link, timeout=12)
                    except Exception as e:  # noqa: BLE001
                        logger.debug("fetch %s failed: %s", link, e)
                        continue
                    if page.status_code != 200:
                        continue
                    job = self._parse_page(link, page.text)
                    if job:
                        jobs.append(job)
                if len(jobs) >= limit:
                    break
        except Exception as e:  # noqa: BLE001 - one source must not break discovery
            logger.warning("Search-engine discovery failed: %s", e)
        return jobs[:limit]
