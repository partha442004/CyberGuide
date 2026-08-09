"""
Apna.co scraper for the Indian job market.

Apna (apna.co) is a large India-first job board (88k+ live vacancies). Its
search result pages are server-rendered by Next.js: the job cards live inside
the `self.__next_f.push(...)` flight payload as a double-escaped JSON
`jobsList` array. There is no public JSON API and the HTML cards themselves
are not present server-side, so this scraper finds the `jobsList` blob inside
the script chunk, un-escapes it once, and pulls each job's fields with
targeted regexes (the blob is not always strict JSON — it may contain
unquoted `$undefined` tokens — so field regexes are more robust than a full
json.loads).

Verified live against `https://apna.co/jobs/cyber-security-jobs-in-bengaluru`:
25 real postings with title, organisation, INR salary, city, WFH flag and a
job detail URL (`/job/{city}/{slug}-{jobID}`).

URL scheme:
- keyword            : https://apna.co/jobs/{slug}-jobs
- keyword + location : https://apna.co/jobs/{slug}-jobs-in-{city-slug}
"""

import logging
import re

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)

# Canonical apna city slugs for the "-in-{city}" URL suffix. These match the
# city slugs apna itself uses in its job URLs / search pages.
_APNA_CITY_SLUGS: dict[str, str] = {
    "bangalore": "bengaluru-bangalore",
    "bengaluru": "bengaluru-bangalore",
    "chennai": "chennai-region",
    "mumbai": "mumbai-bombay",
    "bombay": "mumbai-bombay",
    "delhi": "delhi-ncr",
    "new delhi": "delhi-ncr",
    "ncr": "delhi-ncr",
    "hyderabad": "hyderabad-region",
    "secunderabad": "hyderabad-region",
    "pune": "pune",
    "kolkata": "kolkata",
    "jaipur": "jaipur",
    "gurgaon": "gurgaon-gurugram",
    "gurugram": "gurgaon-gurugram",
    "noida": "noida",
    "kochi": "kochi",
    "kochin": "kochi",
    "coimbatore": "coimbatore",
    "ahmedabad": "ahmedabad",
}

# Remote markers inside the jobCardAddress field.
_REMOTE_MARKERS = ("work from home", "wfh", "remote", "anywhere")

# Apna's curated "security" feed mixes real cybersecurity roles (SOC, SIEM,
# pentest) with physical-security guard roles ("Security Head Ex-Army Man",
# "Security Manager @ Sai International Security" — a guard agency). A VAPT /
# SOC user doesn't want guard jobs, so titles carrying any of these markers
# are rejected outright.
_GUARD_ROLE_MARKERS = (
    "security guard",
    "security officer",
    "security supervisor",
    "security head",
    "security manager",
    "armed",
    "watchman",
    "ex-army",
    "ex army",
    "gatekeeper",
    "bouncer",
    "housekeeping",
    "driver",
)

# Apna serves a real keyword-indexed page for a small set of curated slugs;
# most multi-word queries ("cybersecurity", "soc analyst", ...) fall back to a
# rotating generic feed that never matches. When a query belongs to a domain
# whose curated slug is known to work, the scraper retries with that slug so
# the user still gets real listings (verified live: `security` returns real
# SOC / SIEM / security roles).
_CURATED_FALLBACKS: dict[str, str] = {
    "security": "security",
    "cybersecurity": "security",
    "cyber security": "security",
    "cyber": "security",
    "infosec": "security",
    "soc": "security",
    "soc analyst": "security",
    "security analyst": "security",
    "security engineer": "security",
    "security manager": "security",
    "vapt": "security",
    "penetration testing": "security",
    "penetration test": "security",
    "ethical hacking": "security",
    "information security": "security",
    "network security": "security",
    "application security": "security",
    "cloud security": "security",
    "security operations": "security",
    "incident response": "security",
    "cyber defense": "security",
    "blue team": "security",
    "devsecops": "security",
    "frontend": "frontend developer",
    "frontend developer": "frontend developer",
    "front end developer": "frontend developer",
    "react developer": "frontend developer",
    "ui developer": "frontend developer",
    "angular developer": "frontend developer",
    "javascript developer": "frontend developer",
}


class ApnaScraper(BaseScraper):
    """Scraper for apna.co job postings."""

    BASE_URL = "https://apna.co"

    @property
    def source_name(self) -> str:
        return "apna"

    @property
    def rate_limit(self) -> int:
        return 15  # Conservative rate limit

    @staticmethod
    def _slug(text: str) -> str:
        """Lowercase alphanumerics joined by hyphens (like apna's slugs)."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "jobs"

    def _search_url(self, query: str, location: str | None) -> str:
        """Build the apna keyword (+location) search URL."""
        slug = self._slug(query)
        path = f"/jobs/{slug}-jobs"
        if location:
            city = _APNA_CITY_SLUGS.get(location.lower().strip())
            if city:
                path += f"-in-{city}"
        return f"{self.BASE_URL}{path}"

    @staticmethod
    def _fallback_query(query: str) -> str | None:
        """Curated apna keyword for this query, or None.

        Multi-word queries ("cybersecurity", "soc analyst") don't have their
        own index on apna — they render a rotating generic feed. This maps
        them to the closest curated slug that actually returns matching jobs.
        The `<skill> intern` / `<skill> internship` queries the scheduler
        appends are stripped of their suffix first, so "vapt intern" still
        resolves to the "security" feed.
        """
        key = query.strip().lower()
        stripped = re.sub(r"\s+(intern|internship)s?$", "", key)
        for candidate in (key, stripped):
            if candidate in _CURATED_FALLBACKS:
                fb = _CURATED_FALLBACKS[candidate]
                return fb if fb != candidate else None
        return None

    @staticmethod
    def _unescape_script(html: str) -> str:
        """Pull the script chunk holding `jobsList` and un-escape it once.

        The flight payload is a JS string where JSON quotes are escaped as
        `\\"` (and, inside that, `\\\\"` at the raw-HTML level). After the
        single un-escape the payload is normal JSON-ish text we can regex.
        """
        idx = html.find("jobsList")
        if idx == -1:
            return ""
        start = html.rfind("<script", 0, idx)
        end = html.find("</script>", idx)
        if start == -1 or end == -1:
            return ""
        script = html[start:end]
        # Raw-HTML level: \\" (four chars) -> \" ; then \" -> ".
        return (
            script.replace('\\\\"', '"')
            .replace('\\"', '"')
            .replace("\\\\/", "/")
            .replace("\\u0026", "&")
            .replace("\\u002F", "/")
        )

    @staticmethod
    def _extract_field_pairs(payload: str) -> list[dict]:
        """Pull aligned job fields from the un-escaped jobsList payload.

        Every job object contains `jobID`, `jobTitle`, `organisationName`,
        `jobPublicURL`, `jobCardAddress` and `jobSalaryRangeDetails` (in that
        relative order inside each object), so we zip the per-field regex
        lists by index. This is robust to the payload not being strict JSON
        (unquoted `$undefined` tokens) and to nested `]` inside strings.
        """
        job_ids = re.findall(r'"jobID":(\d+)', payload)
        titles = re.findall(r'"jobTitle":"([^"]+)"', payload)
        orgs = re.findall(r'"organisationName":"([^"]+)"', payload)
        urls = re.findall(r'"jobPublicURL":"([^"]+)"', payload)
        addrs = re.findall(r'"jobCardAddress":"([^"]+)"', payload)
        # salaryMax / salaryMin appear in one object each; regex may miss when
        # they're separated by more than the usual short gap, so be lenient.
        sals = re.findall(r"salaryMax.:(\d+).*?salaryMin.:(\d+)", payload)

        out: list[dict] = []
        for i, title in enumerate(titles):
            raw_id = job_ids[i] if i < len(job_ids) else None
            try:
                job_id = int(raw_id) if raw_id else None
            except (TypeError, ValueError):
                job_id = None
            out.append(
                {
                    "job_id": job_id,
                    "title": title,
                    "organisation": orgs[i] if i < len(orgs) else "Unknown",
                    "public_url": urls[i] if i < len(urls) else None,
                    "address": addrs[i] if i < len(addrs) else None,
                    "salary_max": int(sals[i][0]) if i < len(sals) else None,
                    "salary_min": int(sals[i][1]) if i < len(sals) else None,
                }
            )
        return out

    async def _fetch_url(self, url: str, query: str, limit: int) -> list[RawJob]:
        """Fetch + filter one apna URL; never raises."""
        jobs: list[RawJob] = []
        try:
            response = await self._get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-IN,en;q=0.9",
                },
            )
            if response.status_code != 200:
                logger.warning("Apna fetch %s -> %s", url, response.status_code)
                return jobs

            payload = self._unescape_script(response.text)
            if not payload:
                logger.warning("Apna page %s has no jobsList payload", url)
                return jobs

            for item in self._extract_field_pairs(payload):
                title = (item["title"] or "").strip()
                if not title:
                    continue
                # Precision filter: the keyword page may carry loosely related
                # postings (e.g. "Customer Care Executive" on a security
                # search), so only keep jobs that match the query.
                if not matches_query(title, query, title=title):
                    continue
                # Physical-security guard roles ("Security Head Ex-Army Man")
                # are not cybersecurity — drop them so a VAPT/SOC user never
                # gets guard listings in their digest.
                title_lower = title.lower()
                if any(m in title_lower for m in _GUARD_ROLE_MARKERS):
                    continue

                address = (item["address"] or "").strip()
                is_remote = any(m in address.lower() for m in _REMOTE_MARKERS)
                jobs.append(
                    RawJob(
                        title=title,
                        company=(
                            (item["organisation"] or "Unknown").strip() or "Unknown"
                        ),
                        url=(
                            f"{self.BASE_URL}{item['public_url']}"
                            if item["public_url"]
                            else f"{url}#job-{item['job_id']}"
                        ),
                        location=address or None,
                        salary_min=item["salary_min"],
                        salary_max=item["salary_max"],
                        salary_currency="INR",
                        is_remote=is_remote,
                        source="apna",
                        raw_data={"apna_job_id": item["job_id"]},
                    )
                )
                if len(jobs) >= limit:
                    break
        except Exception as e:  # noqa: BLE001 - scraper must never raise
            logger.error("Error fetching from Apna (%s): %s", url, e)
        return jobs

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from apna.co for the keyword (+ optional city).

        Tries the literal query slug first; when it yields nothing (apna
        serves a generic feed for most multi-word slugs), retries with the
        curated fallback keyword for the domain so real listings still come
        through. Falls back to the plain (city-less) URL too, since not
        every slug has a city page.
        """
        candidates: list[str] = [self._search_url(query, location)]
        fallback = self._fallback_query(query)
        if fallback:
            fb_url = self._search_url(fallback, location)
            if fb_url not in candidates:
                candidates.append(fb_url)
        plain = self._search_url(query, None)
        if plain not in candidates:
            candidates.append(plain)
        if fallback:
            fb_plain = self._search_url(fallback, None)
            if fb_plain not in candidates:
                candidates.append(fb_plain)

        seen: set = set()
        jobs: list[RawJob] = []
        # Fetch candidates until we have enough real matches. A thin first
        # result (e.g. a single weak match from the city-exact page) must not
        # suppress the richer curated fallback (the plain "security" page),
        # so we only stop early once we're comfortably at the target size.
        target = max(1, min(limit, 5))
        for url in candidates:
            for job in await self._fetch_url(url, query, limit):
                key = (job.title, job.url)
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
                if len(jobs) >= limit:
                    return jobs
            if len(jobs) >= target:
                break
        return jobs
