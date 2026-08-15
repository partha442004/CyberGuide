"""
Freshersworld scraper — India's #1 fresher job board (TeamLease).

Freshersworld is a generalist fresher board, so its keyword ``/jobs`` page
ignores query parameters server-side (search is a JS SPA). The stable
city pages (``/jobs-in-{city}/{code}``) DO render 20 real posting cards per
page with direct application URLs in the ``job_display_url`` attribute of
each ``job-container`` div.

Because the city pages are generalist, cards are filtered with
``matches_query`` (the same relevance filter every other scraper uses) so a
"cyber security" discovery query keeps only security-family roles instead of
telecaller / business-development listings. Salary is parsed from the
``15000 Monthly`` / ``3.5 LPA`` style qualification spans.
"""

import logging
import re
from datetime import UTC, datetime

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)

# City slug -> numeric code from the site's own /jobs-by-cities links.
# Only the metros are mapped; unknown locations fall back to the general
# /jobs page (the digest filters by user location downstream anyway).
_CITY_CODES: dict[str, str] = {
    "ahmedabad": "9999011030",
    "bangalore": "9999016065",
    "chennai": "99990300125",
    "delhi": "9999035",
    "gurgaon": "9999012049",
    "hyderabad": "999903705",
    "kolkata": "99990340160",
    "mumbai": "9999020093",
    "noida": "99990320152",
    "pune": "9999020098",
}

# Alias map so "Bengaluru", "New Delhi" etc. resolve to a known city slug.
_CITY_ALIASES = {
    "bengaluru": "bangalore",
    "banglore": "bangalore",
    "new delhi": "delhi",
    "delhi ncr": "delhi",
    "gurugram": "gurgaon",
    "kolkatta": "kolkata",
    "calcutta": "kolkata",
    "bombay": "mumbai",
    "pune city": "pune",
}

# Card container opening tag: carries the direct application URL.
_CARD_OPEN = re.compile(r'<div[^>]*class="[^"]*job-container[^"]*"[^>]*>', re.DOTALL)
_JOB_DISPLAY_URL = re.compile(r'job_display_url="([^"]+)"')
_JOB_ID = re.compile(r'job_id="(\d+)"')
_TITLE = re.compile(r'<span class="wrap-title seo_title">\s*([^<]+?)\s*<', re.DOTALL)
_COMPANY = re.compile(
    r'<h3 class="latest-jobs-title[^"]*company-name">\s*([^<]+?)\s*</h3>',
    re.DOTALL,
)
_LOCATION = re.compile(
    r'class="job-location[^"]*">\s*<span class=\'bold_elig\'>([^<]+?)</span>',
    re.DOTALL,
)
_EXPERIENCE = re.compile(
    r'class="experience[^"]*"[^>]*>\s*([^<]+?)\s*</span>', re.DOTALL
)
# Salary lives in the qualifications span, e.g. "15000 Monthly" / "3.5 LPA".
_SALARY = re.compile(
    r'class="qualifications[^"]*"[^>]*>\s*([^<]+?)\s*</span>', re.DOTALL
)
_POSTED = re.compile(r'class="desc">\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\s*', re.DOTALL)

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _city_slug(location: str | None) -> str | None:
    """Normalise a free-text location into a known Freshersworld city slug."""
    if not location:
        return None
    slug = re.sub(r"[^a-z\s]", "", location.strip().lower())
    slug = re.sub(r"\s+", " ", slug).strip()
    # Strip common suffixes ("city", "india", "karnataka" ...).
    for suffix in ("city", "india", "karnataka", "tamil nadu", "maharashtra"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)].strip()
    slug = _CITY_ALIASES.get(slug, slug)
    return slug if slug in _CITY_CODES else None


def _parse_salary(text: str | None) -> tuple[int | None, int | None]:
    """Parse an INR salary like '15000 Monthly' or '3.5 LPA' -> (min, max)."""
    if not text:
        return (None, None)
    t = text.strip()
    m = re.search(r"([\d,]+(?:\.\d+)?)", t)
    if not m:
        return (None, None)
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return (None, None)
    if "lpa" in t.lower() or "lakh" in t.lower():
        value = value * 100_000
    elif "monthly" in t.lower() or "per month" in t.lower():
        value = value * 12
    return (int(value), int(value))


def _parse_posted(text: str | None) -> datetime | None:
    """Parse a '15 August 2026' posted date."""
    if not text:
        return None
    m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*", text)
    if not m:
        return None
    day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    month = _MONTHS.get(month_name)
    if not month:
        return None
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


class FreshersworldScraper(BaseScraper):
    """Scrape freshersworld.com city job-list pages."""

    BASE_URL = "https://www.freshersworld.com"

    @property
    def source_name(self) -> str:
        return "freshersworld"

    def _search_url(self, location: str | None = None) -> str:
        slug = _city_slug(location)
        if slug:
            return f"{self.BASE_URL}/jobs-in-{slug}/{_CITY_CODES[slug]}"
        return f"{self.BASE_URL}/jobs"

    def _extract_cards(self, html: str) -> list[dict]:
        """Parse job cards into {title, company, url, location, ...} dicts."""
        out: list[dict] = []
        seen: set[str] = set()
        for m in _CARD_OPEN.finditer(html):
            open_tag = m.group(0)
            url_m = _JOB_DISPLAY_URL.search(open_tag)
            if not url_m:
                continue
            url = url_m.group(1).strip()
            if not url or url in seen:
                continue
            window = html[m.end() : m.end() + 4000]
            title_m = _TITLE.search(window)
            title = title_m.group(1).strip() if title_m else ""
            if not title:
                continue
            company_m = _COMPANY.search(window)
            company = company_m.group(1).strip() if company_m else "Unknown"
            loc_m = _LOCATION.search(window)
            location = loc_m.group(1).strip() if loc_m else None
            exp_m = _EXPERIENCE.search(window)
            experience = exp_m.group(1).strip() if exp_m else None
            sal_m = _SALARY.search(window)
            salary = sal_m.group(1).strip() if sal_m else None
            posted_m = _POSTED.search(window)
            posted = _parse_posted(posted_m.group(1)) if posted_m else None
            seen.add(url)
            out.append(
                {
                    "title": title,
                    "company": company,
                    "url": url,
                    "location": location,
                    "experience": experience,
                    "salary": salary,
                    "posted_at": posted,
                }
            )
        return out

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 50
    ) -> list[RawJob]:
        import httpx

        search_url = self._search_url(location)
        jobs: list[RawJob] = []
        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                },
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    logger.warning(
                        "Freshersworld returned %d for %s",
                        resp.status_code,
                        search_url,
                    )
                    return jobs
                for card in self._extract_cards(resp.text):
                    title = card["title"]
                    if not matches_query(title, query):
                        continue
                    sal_min, sal_max = _parse_salary(card["salary"])
                    jobs.append(
                        RawJob(
                            title=title,
                            company=card["company"],
                            url=card["url"],
                            location=card["location"],
                            salary_min=sal_min,
                            salary_max=sal_max,
                            salary_currency="INR",
                            posted_at=card["posted_at"],
                            tags=["fresher"],
                            source=self.source_name,
                            raw_data={
                                "experience": card["experience"],
                                "salary_text": card["salary"],
                            },
                        )
                    )
                    if len(jobs) >= limit:
                        break
        except Exception as e:  # noqa: BLE001 - scraper never raises
            logger.warning("Freshersworld scrape failed for %s: %s", query, e)
        return jobs
