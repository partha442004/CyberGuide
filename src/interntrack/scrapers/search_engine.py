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
import time
from urllib.parse import parse_qs, parse_qsl, urlparse

from interntrack.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)

# Wall-clock budget for one ``fetch`` call (seconds). Bounds the search
# engine so the daily discovery slot's shared 38s serverless budget is
# split across every member's queries instead of being consumed by the
# first query's ~90 site: searches.
_SEARCH_ENGINE_FETCH_BUDGET_SECONDS = 8

# Query sent to DuckDuckGo per keyword (HTML endpoint, no key).
_SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"

# Bing fallback (HTML, no key) — DDG blocks some datacenter IPs, Bing
# tolerates them and can be pinned to the Indian market.
_BING_URL = "https://www.bing.com/search?mkt=en-IN&setlang=en&q={query}"

# Brave third engine (HTML, no key) — indexes internship/fresher boards
# (internshala, jooble, makeintern, ...) that DDG/Bing rank lower, and
# tolerates datacenter IPs. Results are plain external hrefs. Brave
# serves a JS shell to non-browser user agents, so the Brave requests
# carry a Chrome UA (the app UA stays for every other request).
_BRAVE_URL = "https://search.brave.com/search?q={query}"
_BRAVE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

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
    "jobdexo.com",
    "freshersworld.com",
    "unstop.com",
    "hackerearth.com",
    "instahyre.com",
    "hirist.com",
    "lever.co",
    "greenhouse.io",
    "ashbyhq.com",
    "workable.com",
    "bamboohr.com",
    "smartrecruiters.com",
    # Cybersecurity-specific boards.
    "cybersecurityjobs.com",
    "cybersecurityjobsite.com",
    "cybersn.com",
    "clearedjobs.net",
    "infosec-jobs.com",
    "securityjobs.net",
    "ninjajobs.com",
    "techfetch.com",
    # Government / sarkari job portals.
    "sarkariresult.com",
    "freejobalert.com",
    "sarkariexam.com",
    "sarkarijobfind.com",
    "indgovtjobs.in",
    # Job aggregators.
    "simplyhired",
    "jooble",
    "talent.com",
    "careerjet",
    "adzuna",
    "ziprecruiter.com",
    "jora.com",
    "trovit",
    "careerbliss.com",
    "careerage.com",
    # Remote-first boards.
    "remote.co",
    "jobspresso.co",
    "workingnomads.com",
    "flexjobs.com",
    "virtualvocations.com",
    "nordesk.io",
    "justremote.co",
    "remoteok.com",
    "authenticjobs.com",
    "pangian.com",
    # More India boards + student platforms.
    "fresherslive.com",
    "workindia.in",
    "youth4work.com",
    "placementindia.com",
    "prosple.com",
    "twenty19.com",
    "letsintern.com",
    "hellointern.com",
    # More cybersecurity boards.
    "cybersecpeople.com",
    "cybersec4u.com",
    "dice.com",
    # More India boards + govt portals.
    "careernet.co.in",
    "iimjobs.com",
    "elitmus.com",
    "aasaanjobs.com",
    "rojgarresult.com",
    "employmentnews.gov.in",
    "apprenticeshipindia.gov.in",
    # Global boards.
    "themuse.com",
    "builtin.com",
    "ladders.com",
    "snagajob.com",
    "getwork.com",
    "jobcase.com",
    "jobrapido.com",
    "jobserve.com",
    # Startup / tech boards.
    "workatastartup.com",
    "otta.com",
    "cord.co",
    "landing.jobs",
    "turing.com",
    "gun.io",
    "contra.com",
    "usebraintrust.com",
    "arc.dev",
    # Bug bounty / security communities.
    "hackerone.com",
    "bugcrowd.com",
    "intigriti.com",
    "yeswehack.com",
    "isc2.org",
    "isaca.org",
    "issa.org",
    "sans.org",
    "owasp.org",
    # Research / academic.
    "researchgate.net",
    "nature.com",
    "jobs.ac.uk",
    "ieee.org",
    "acm.org",
    # More remote boards.
    "jobicy.com",
    "remotejobs.com",
    "remote3.co",
    "remote100k.com",
    "remotees.com",
    "skipthedrive.com",
    "remotelyawesomejobs.com",
    # ATS career portals.
    "myworkdayjobs.com",
    "icims.com",
    "jobvite.com",
    "taleo.net",
    "successfactors.eu",
    "recruitee.com",
    "pinpoint.world",
    "teamtailor.com",
    "jazzhr.com",
    "breezy.hr",
    # More bug bounty / security-research platforms.
    "hackenproof.com",
    "synack.com",
    "immunefi.com",
    "code4rena.com",
    "sherlock.xyz",
    # Research / structured programs (paid opportunities, not just jobs).
    "summerofcode.withgoogle.com",
    "outreachy.org",
    "mlh.io",
    "linuxfoundation.org",
    "cncf.io",
    # Big-tech career pages / internship portals.
    "careers.google.com",
    "careers.microsoft.com",
    "university.microsoft.com",
    "amazon.jobs",
    "careers.cisco.com",
    "jobs.ibm.com",
    "careers.qualcomm.com",
    "jobs.intel.com",
    "careers.adobe.com",
    "careers.salesforce.com",
    # University placement / internship cells (India).
    "placement.iitm.ac.in",
    "ccd.iitd.ac.in",
    "placement.iitb.ac.in",
    "cdc.iitkgp.ac.in",
    "placement.iisc.ac.in",
    # Govt / defence / regulatory recruitment portals.
    "drdo.gov.in",
    "isro.gov.in",
    "nic.in",
    "cdac.in",
    "nielit.gov.in",
    "bel-india.in",
    "hal-india.com",
    "ecil.co.in",
    "bhel.com",
    "rbi.org.in",
    "sebi.gov.in",
    "npci.org.in",
    "uidai.gov.in",
    "cert-in.org.in",
    # Apprenticeship / trainee schemes.
    "naps.gov.in",
    # International government / public-sector job boards.
    "usajobs.gov",
    "civilservicejobs.service.gov.uk",
    "jobs.nhs.uk",
    "apsjobs.gov.au",
    "jobs-emplois.gc.ca",
    "epso.europa.eu",
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
    # Plural "…-internships" slugs are category pages (Internshala); the
    # singular /internships/<role> paths are real postings and pass.
    "-internships",
    # Internshala category pages also use singular slugs
    # (<role>-internship-in-<city>[/stipend-<amt>]) — listings, not postings.
    "-internship-in-",
    "/stipend-",
    "/posts/",
    "/pulse/",  # LinkedIn Pulse = content articles, never job postings
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
    # Company / university career-portal posting shapes: company.com/careers/<role>,
    # /jobs/<role>, /internships/<role>. The bare roots are rejected separately.
    "/careers/",
    "/internships/",
    "/jobs/",
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

# Career-portal roots that are listing pages, never individual postings
# (company.com/careers, university.edu/internships …). Paths *under* them
# (/careers/security-engineer, /internships/summer-analyst) are postings.
_LISTING_ROOTS = frozenset(
    {
        "careers",
        "career",
        "jobs",
        "internships",
        "internship",
        "opportunities",
        "openings",
        "positions",
        "position",
        "vacancies",
        "vacancy",
    }
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
    "amazon.in",
    "amazon.com",
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

# Titles that are content-marketing articles rather than job postings.
# LinkedIn (and some boards) repurpose posting URLs for article/pulse
# content, so a search result can carry a non-job title like
# "15 Best Chess Opening Moves That You Absolutely Must Know" — these are
# never jobs and must be dropped, not saved.
_JUNK_TITLE_RE = re.compile(
    r"^\d+\s+(best|top|tips?|ways|reasons|things|moves|ideas?|books|tools|"
    r"skills|tricks)\b"
    r"|^top\s+\d+\b"
    r"|\b(you (absolutely )?must know|you need to know|to know in \d+|to avoid|"
    r"to master|to succeed|check out|watch out for)\b"
    r"|\b(ultimate guide|beginner'?s? guide|how to (become|get|learn|land|"
    r"break into))\b"
    r"|\b(here'?s? (how|what|why)|why you should|the best way)\b"
    r"|\bwhat does (a|an|the)?\s*[a-z]+\s*(do|mean)\b"
    r"|\bwhat (is|are) (a|an|the)?\s*[a-z]+\b"
    r"|\b(day in the life|career (explorer|path|profile|outlook))\b",
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
    def _brave_links(html: str) -> list[str]:
        """Extract organic result URLs from a Brave results page.

        Brave renders results as plain external ``<a href>`` links (no
        redirect wrapper); internal chrome (settings, ads, the Brave
        homepage, CDN assets) is filtered out and ``&amp;`` is decoded.
        ``_is_job_url`` downstream drops everything that isn't a posting.
        """
        links: list[str] = []
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            href = m.group(1).replace("&amp;", "&")
            if any(skip in href for skip in ("brave.com", "bravesoftware")):
                continue
            if href not in links:
                links.append(href)
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
            resp = await self._get(url, timeout=10)
            return self._bing_links(resp.text)
        if engine == "brave":
            url = _BRAVE_URL.format(query=urllib.parse.quote_plus(query))
            resp = await self._get(url, timeout=10, headers={"User-Agent": _BRAVE_UA})
            return self._brave_links(resp.text)
        url = _SEARCH_URL.format(query=urllib.parse.quote_plus(query))
        resp = await self._get(url, timeout=10)
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
        # PDF recruitment notices (govt / university / walk-in drives) are
        # individual documents, never listing pages.
        if parsed.path.lower().endswith(".pdf"):
            return True
        if any(marker in full for marker in _LISTING_MARKERS):
            return False
        # A bare host root (jobs.lever.co/, app landing, board homepage) is
        # never an individual posting.
        if path in ("", "/", "/index.html", "/index.htm"):
            return False
        # A career-portal root (company.com/careers, university.edu/internships)
        # is a listing, never a posting — but specific paths under it are.
        segments = [s for s in path.split("/") if s]
        if len(segments) == 1 and segments[0] in _LISTING_ROOTS:
            return False
        if any(h in host for h in _JOB_HOSTS):
            return True
        return any(marker in path for marker in _POSTING_MARKERS)

    def _parse_pdf(self, url: str, content: bytes) -> RawJob | None:
        """Extract a recruitment-notice PDF into a RawJob (best-effort).

        A lot of Indian internships / govt recruitment is announced as PDFs
        (Recruitment_2026.pdf, Walk-in_Interview.pdf …). Text extraction is
        imperfect across PDF generators, so this never raises and returns
        ``None`` when the PDF is unreadable. Title = the first readable
        lines of the notice; company = the serving host.
        """
        try:
            from io import BytesIO

            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            first_page = (reader.pages[0].extract_text() or "").strip()
            pages_text = "\n".join(
                (page.extract_text() or "") for page in reader.pages[:5]
            )
        except Exception:  # noqa: BLE001 - PDF generators vary wildly
            return None
        full = re.sub(r"\s+", " ", pages_text).strip()
        if len(full) < 20:
            return None
        # Product guides / whitepapers / credit-scheme PDFs are documents,
        # not recruitment notices — a notice talks about a role/eligibility.
        # The generic junk-title rules catch listicles; add document-y
        # markers here so a guide PDF never becomes a "job".
        if _JUNK_TITLE_RE.search(full[:300]) or re.search(
            r"\b(credits? guide|whitepaper|white paper|product guide|user guide|"
            r"terms? of service|privacy policy|brochure)\b",
            full[:300],
            re.IGNORECASE,
        ):
            return None
        host = urlparse(url).netloc.replace("www.", "")
        company = host.split(".")[0].title() if host else "Unknown"
        lines = [ln.strip() for ln in first_page.splitlines() if ln.strip()]
        title = (
            " ".join(lines[:2]) or full[:120] or f"Recruitment notice — {company}"
        )[:140]
        return RawJob(
            title=title,
            company=company[:200],
            url=url,
            source=self.source_name,
            description=full[:2000] or None,
        )

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
        if not title or _LISTING_TITLE_RE.search(title) or _JUNK_TITLE_RE.search(title):
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
        # wellfound, foundit/timesjobs/hirect, naukri/shine/freshersworld/
        # unstop, plus the cybersecurity boards).
        queries = [
            f"{q} job OR vacancy OR opening",
            f"{q} internship OR fresher OR career",
            # LinkedIn is the single biggest source but its guest jobs API
            # auth-walls datacenter IPs, so the direct scraper returns 0.
            # The posting URLs are still indexed — surface them through the
            # search engines (and the India mirror) to keep LinkedIn fresh.
            f"site:linkedin.com/jobs OR site:in.linkedin.com/jobs {q}",
            f"site:cutshort.io {q}",
            f"site:wellfound.com {q}",
            (
                f"site:foundit.in OR site:timesjobs.com OR site:hirect.in "
                f"OR site:jobdexo.com {q}"
            ),
            (
                f"site:naukri.com OR site:shine.com OR site:freshersworld.com "
                f"OR site:unstop.com OR site:instahyre.com OR site:hirist.com {q}"
            ),
            # Internship-focused boards (Internshala listings are rejected as
            # listing pages, but their individual postings and the other
            # intern boards' postings surface through this query).
            f"site:internshala.com OR site:in.indeed.com/internships {q}",
            (
                f"site:cybersecurityjobs.com OR site:cybersecurityjobsite.com "
                f"OR site:cybersn.com OR site:clearedjobs.net {q}"
            ),
            (
                f"site:infosec-jobs.com OR site:securityjobs.net "
                f"OR site:ninjajobs.com OR site:techfetch.com {q}"
            ),
            # ATS career boards (Greenhouse / Lever / Ashby / SmartRecruiters)
            # — direct company postings that are fully indexed.
            (
                f"site:boards.greenhouse.io OR site:jobs.lever.co "
                f"OR site:jobs.ashbyhq.com OR site:careers.smartrecruiters.com {q}"
            ),
            # More India job boards (Monster/Foundit mirror, Glassdoor IN,
            # CareerBuilder India, Apna, JobHai, Shine already above).
            (
                f"site:glassdoor.co.in OR site:careerbuilder.co.in "
                f"OR site:monsterindia.com OR site:jobhai.com {q}"
            ),
            # Government / sarkari job portals (India).
            (
                f"site:sarkariresult.com OR site:freejobalert.com "
                f"OR site:sarkariexam.com OR site:sarkarijobfind.com "
                f"OR site:indgovtjobs.in {q}"
            ),
            # Job aggregators (index everything, so postings surface via
            # the search engines without ever touching their APIs).
            (
                f"site:simplyhired.co.in OR site:jooble.org OR site:talent.com "
                f"OR site:careerjet.in OR site:adzuna.in {q}"
            ),
            (
                f"site:ziprecruiter.com OR site:jora.com OR site:trovit.co.in "
                f"OR site:careerbliss.com OR site:careerage.com {q}"
            ),
            # Remote-first boards (remote / WFH / anywhere roles).
            (
                f"site:remote.co OR site:jobspresso.co OR site:workingnomads.com "
                f"OR site:flexjobs.com OR site:virtualvocations.com {q}"
            ),
            (
                f"site:nordesk.io OR site:justremote.co OR site:remoteok.com "
                f"OR site:authenticjobs.com OR site:pangian.com {q}"
            ),
            # More India boards + student/internship platforms.
            (
                f"site:fresherslive.com OR site:workindia.in OR site:youth4work.com "
                f"OR site:placementindia.com OR site:careerage.com {q}"
            ),
            (
                f"site:prosple.com OR site:twenty19.com OR site:letsintern.com "
                f"OR site:hellointern.com OR site:internshala.com/internships {q}"
            ),
            # Cybersecurity-specific boards (more of them).
            (
                f"site:cybersecpeople.com OR site:cybersec4u.com "
                f"OR site:securityjobs.net OR site:clearedjobs.net OR site:dice.com {q}"
            ),
            # More India boards (CareerNet / iimjobs / eLitmus / AasaanJobs /
            # WorkIndia / Rojgar Result / Employment News / NATS).
            (
                f"site:careernet.co.in OR site:iimjobs.com OR site:elitmus.com "
                f"OR site:aasaanjobs.com OR site:rojgarresult.com {q}"
            ),
            (
                f"site:employmentnews.gov.in OR site:nats.education.gov.in "
                f"OR site:apprenticeshipindia.gov.in OR site:superset.com {q}"
            ),
            # Global boards (The Muse / Built In / Ladders / Snagajob /
            # Getwork / Jobcase / Jobrapido / JobServe).
            (
                f"site:themuse.com OR site:builtin.com OR site:ladders.com "
                f"OR site:snagajob.com OR site:getwork.com {q}"
            ),
            (
                f"site:jobcase.com OR site:jobrapido.com OR site:jobserve.com "
                f"OR site:careerbliss.com {q}"
            ),
            # Startup / tech boards (YC / Otta / Cord / Landing.jobs / Turing /
            # Arc / Gun.io / Contra / Braintrust).
            (
                f"site:workatastartup.com OR site:otta.com OR site:cord.co "
                f"OR site:landing.jobs OR site:turing.com {q}"
            ),
            (
                f"site:gun.io OR site:contra.com OR site:usebraintrust.com "
                f"OR site:arc.dev {q}"
            ),
            # Bug bounty / security-community platforms.
            (
                f"site:hackerone.com OR site:bugcrowd.com OR site:intigriti.com "
                f"OR site:yeswehack.com {q}"
            ),
            (
                f"site:isc2.org OR site:isaca.org OR site:issa.org "
                f"OR site:sans.org OR site:owasp.org {q}"
            ),
            # Research / academic job boards.
            (
                f"site:researchgate.net OR site:nature.com/naturecareers "
                f"OR site:science.org/careers OR site:jobs.ac.uk {q}"
            ),
            (f"site:ieee.org OR site:acm.org OR site:careers.ieee.org {q}"),
            # More remote boards (Jobicy / RemoteJobs.com / Remote3 /
            # Remote100K / Remotees / SkipTheDrive).
            (
                f"site:jobicy.com OR site:remotejobs.com OR site:remote3.co "
                f"OR site:remote100k.com OR site:remotees.com {q}"
            ),
            (
                f"site:skipthedrive.com OR site:remotelyawesomejobs.com "
                f"OR site:virtualvocations.com OR site:authenticjobs.com {q}"
            ),
            # ATS career portals (Workday / iCIMS / Jobvite / Taleo /
            # SuccessFactors / Recruitee / Pinpoint / Teamtailor / JazzHR /
            # Breezy HR). These host most company career pages directly.
            (
                f"site:myworkdayjobs.com OR site:icims.com/jobs "
                f"OR site:jobvite.com OR site:taleo.net {q}"
            ),
            (
                f"site:successfactors.eu OR site:recruitee.com "
                f"OR site:pinpoint.world OR site:teamtailor.com {q}"
            ),
            (f"site:jazzhr.com OR site:breezy.hr OR site:bamboohr.com/jobs {q}"),
            # More bug bounty / security-research platforms (HackenProof /
            # Synack / Immunefi / Code4rena / Sherlock).
            (
                f"site:hackenproof.com OR site:synack.com OR site:immunefi.com "
                f"OR site:code4rena.com OR site:sherlock.xyz {q}"
            ),
            # CTF / cybersecurity learning platforms — talent signals, not
            # postings. Queried so events / competition / recruitment pages
            # still surface, but they are not host-trusted (no digest spam).
            (
                f"site:ctftime.org OR site:tryhackme.com OR site:hackthebox.com "
                f"OR site:portswigger.net OR site:picoctf.org {q}"
            ),
            (
                f"site:cyberdefenders.org OR site:blueteamlabs.online "
                f"OR site:root-me.org OR site:overthewire.org {q}"
            ),
            # Research / structured programs (Google Summer of Code / Outreachy /
            # MLH Fellowship / Linux Foundation / CNCF).
            (
                f"site:summerofcode.withgoogle.com OR site:outreachy.org "
                f"OR site:mlh.io OR site:linuxfoundation.org OR site:cncf.io {q}"
            ),
            # Big-tech internships / graduate careers.
            (
                f"site:careers.google.com OR site:careers.microsoft.com "
                f"OR site:amazon.jobs OR site:university.microsoft.com {q}"
            ),
            (
                f"site:careers.cisco.com OR site:jobs.ibm.com "
                f"OR site:careers.qualcomm.com OR site:jobs.intel.com {q}"
            ),
            (
                f"site:careers.adobe.com OR site:careers.salesforce.com "
                f"OR site:nvidia.com/en-us/about-nvidia/careers {q}"
            ),
            # University placement / internship cells (IIT / IISc / IIIT / NIT).
            (
                f"site:placement.iitm.ac.in OR site:ccd.iitd.ac.in "
                f"OR site:placement.iitb.ac.in OR site:cdc.iitkgp.ac.in {q}"
            ),
            (f"site:placement.iisc.ac.in OR site:nitc.ac.in OR site:iiitb.ac.in {q}"),
            # Govt / defence / regulatory recruitment portals.
            (
                f"site:drdo.gov.in OR site:isro.gov.in OR site:nic.in "
                f"OR site:cdac.in OR site:nielit.gov.in {q}"
            ),
            (
                f"site:bel-india.in OR site:hal-india.com OR site:ecil.co.in "
                f"OR site:bhel.com {q}"
            ),
            (
                f"site:rbi.org.in OR site:sebi.gov.in OR site:npci.org.in "
                f"OR site:uidai.gov.in OR site:cert-in.org.in {q}"
            ),
            # Apprenticeship / trainee schemes (NAPS; NATS already above).
            (f"site:naps.gov.in OR site:apprenticeshipindia.gov.in {q}"),
            # Security communities (events / talks / hiring connections).
            (
                f"site:null.community OR site:defcon.org OR site:bsides.org "
                f"OR site:eccouncil.org {q}"
            ),
            # Direct security-vendor career pages (most run on Workday /
            # Greenhouse, which are queried above; these have own portals).
            (
                f"site:cyberark.com/careers OR site:veracode.com/careers "
                f"OR site:checkmarx.com/company/careers OR site:aquasec.com/careers "
                f"OR site:sailpoint.com/company/careers "
                f"OR site:beyondtrust.com/careers {q}"
            ),
            (
                f"site:eset.com/careers OR site:sonicwall.com/company/careers "
                f"OR site:watchguard.com/about/careers "
                f"OR site:juniper.net/us/en/company/careers "
                f"OR site:pingidentity.com/en/company/careers {q}"
            ),
            (
                f"site:lacework.com/careers OR site:orca.security/careers "
                f"OR site:exabeam.com/company/careers "
                f"OR site:securonix.com/company/careers "
                f"OR site:logrhythm.com/company/careers {q}"
            ),
            (
                f"site:redcanary.com/company/careers "
                f"OR site:bishopfox.com/company/careers "
                f"OR site:trustedsec.com/careers OR site:netspi.com/company/careers "
                f"OR site:horizon3.ai/careers {q}"
            ),
            # Staffing / recruitment agencies (India + global).
            (
                f"site:randstad.co.in OR site:michaelpage.co.in OR site:adecco.co.in "
                f"OR site:teamlease.com OR site:quesscorp.com OR site:cielhr.com {q}"
            ),
            (
                f"site:roberthalf.com OR site:hays.com OR site:kellyservices.com "
                f"OR site:teksystems.com OR site:allegisgroup.com {q}"
            ),
            (
                f"site:cybercoders.com OR site:jeffersonfrank.com "
                f"OR site:harveynash.com OR site:motionrecruitment.com "
                f"OR site:insightglobal.com OR site:experis.com "
                f"OR site:robertwalters.com {q}"
            ),
            # International government / public-sector jobs.
            (
                f"site:usajobs.gov OR site:civilservicejobs.service.gov.uk "
                f"OR site:jobs.nhs.uk OR site:apsjobs.gov.au {q}"
            ),
            (f"site:jobs-emplois.gc.ca OR site:epso.europa.eu {q}"),
            # International student programs (IAESTE / Mitacs / AIESEC /
            # DAAD / Erasmus+).
            (
                f"site:iaeste.org OR site:mitacs.ca OR site:aiesec.org "
                f"OR site:daad.de OR site:erasmus-plus.ec.europa.eu {q}"
            ),
            # Hackathon / hiring-challenge platforms (opportunities, not jobs).
            (
                f"site:devfolio.co OR site:devpost.com OR site:hackerearth.com "
                f"OR site:hackerrank.com OR site:kaggle.com {q}"
            ),
            (
                f"site:topcoder.com OR site:codechef.com OR site:leetcode.com "
                f"OR site:mlh.io OR site:unstop.com {q}"
            ),
            # Freelance / contract marketplaces.
            (
                f"site:upwork.com/jobs OR site:freelancer.com OR site:fiverr.com "
                f"OR site:peopleperhour.com OR site:guru.com OR site:flexiple.com {q}"
            ),
            # Cybersecurity event ecosystems (career fairs / hiring villages).
            (
                f"site:blackhat.com OR site:defcon.org OR site:rsaconference.com "
                f"OR site:bsides.org OR site:nullcon.net OR site:c0c0n.in {q}"
            ),
            # Indian cyber / startup-ecosystem orgs.
            (
                f"site:cybercrime.gov.in OR site:nciipc.gov.in "
                f"OR site:startupindia.gov.in OR site:stpi.in OR site:meity.gov.in {q}"
            ),
            # Professional associations with career resources.
            (
                f"site:cloudsecurityalliance.org OR site:computer.org/careers "
                f"OR site:isc2.org/careers OR site:isaca.org/credentialing {q}"
            ),
            # PDF recruitment notices (govt / university / walk-in drives).
            (f"{q} recruitment notice filetype:pdf"),
            (f"{q} walk-in interview filetype:pdf"),
        ]
        jobs: list[RawJob] = []
        seen: set[str] = set()
        # Give every query a fair slice of the limit instead of letting the
        # first productive query (usually the generic "job OR vacancy" one)
        # eat the whole budget — otherwise the LinkedIn / Naukri / cyber-board
        # ``site:`` queries that surface fresh postings never actually run.
        budget = max(1, limit // len(queries))
        # Hard wall-clock budget for ONE fetch call. The discovery loop gives
        # every user's queries a shared 38s serverless slot; without a cap
        # here the ~90 site: queries × 3 engines × 10s timeouts burned the
        # entire slot on the first user's query, so the other members' jobs
        # were never discovered and their digests arrived empty ("no new
        # security jobs today"). Returning partial results after ~8s lets the
        # next user's query start instead of starving everyone else.
        deadline = time.monotonic() + _SEARCH_ENGINE_FETCH_BUDGET_SECONDS
        try:
            for search in queries:
                if time.monotonic() > deadline:
                    break
                query_cap = len(jobs) + budget
                # DuckDuckGo first; Bing covers the datacenter-IP cases
                # where DDG serves an anomaly page with no result links.
                for engine in ("duckduckgo", "bing", "brave"):
                    if time.monotonic() > deadline:
                        break
                    before = len(jobs)
                    try:
                        found = await self._search_links(engine, search)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("%s search failed for %r: %s", engine, q, e)
                        continue
                    for link in found:
                        if time.monotonic() > deadline:
                            break
                        if not self._is_job_url(link) or link in seen:
                            continue
                        seen.add(link)
                        if len(jobs) >= query_cap:
                            break
                        try:
                            page = await self._get(link, timeout=10)
                        except Exception as e:  # noqa: BLE001
                            logger.debug("fetch %s failed: %s", link, e)
                            continue
                        if page.status_code != 200:
                            continue
                        if link.lower().endswith(".pdf"):
                            job = self._parse_pdf(link, page.content)
                        else:
                            job = self._parse_page(link, page.text)
                        if job:
                            jobs.append(job)
                    # Only move on to the next query when this engine
                    # actually produced jobs — otherwise try the other
                    # engine for the same query (DDG's shaped-but-unparseable
                    # links must not starve Bing).
                    if len(jobs) > before or len(jobs) >= query_cap:
                        break
                if len(jobs) >= limit:
                    break
        except Exception as e:  # noqa: BLE001 - one source must not break discovery
            logger.warning("Search-engine discovery failed: %s", e)
        return jobs[:limit]
