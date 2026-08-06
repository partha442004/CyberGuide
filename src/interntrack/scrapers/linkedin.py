"""
LinkedIn job scraper.

Note: LinkedIn has strict anti-scraping measures. This scraper uses their
public job search page and extracts data from the HTML. Use responsibly
and respect robots.txt.

The guest search API returns server-rendered HTML whose card markup changed
over time. The parser tries the legacy ``result-card`` classes first and then
falls back to the current ``job-search-card`` / ``base-search-card`` markup
(observed live 2026-08), so either structure is handled. Auth-wall responses
(a 999 status or ``authwall``/``challenge`` payloads) are detected and treated
as "no results" rather than crashing the discovery pipeline.
"""

from datetime import datetime

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob

# Markers LinkedIn returns when the guest API is behind a login/challenge wall.
_AUTHWALL_MARKERS = (
    "authwall",
    "challenge",
    "security-verification",
    "captcha",
    "unable to access",
)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job postings."""

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return JobSource.LINKEDIN.value

    @property
    def rate_limit(self) -> int:
        return 10  # Very conservative rate limit

    def _find_first(self, card, tag: str, *classes: str):
        """Return the first element matching ``tag`` with any of ``classes``.

        Legacy class names are listed first so the existing unit tests (which
        mock legacy markup) keep working; on the live guest API the legacy
        classes are absent, so the current ``job-search-card`` classes are
        picked up by the fallback.
        """
        for class_ in classes:
            elem = card.find(tag, class_=class_)
            if elem is not None:
                return elem
        return None

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from LinkedIn."""
        jobs = []

        try:
            params = {
                "keywords": query,
                "start": 0,
                "sortBy": "DD",  # Sort by date
            }
            if location:
                params["location"] = location

            headers = {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.linkedin.com/jobs/",
            }
            response = await self._get(self.BASE_URL, params=params, headers=headers)

            if response.status_code != 200:
                return []

            text = response.text or ""
            lowered = text.lower()
            if any(marker in lowered for marker in _AUTHWALL_MARKERS):
                print("LinkedIn returned an auth wall — skipping source.")
                return []

            # Parse the HTML response. Try the current card markup first, then
            # fall back to the legacy result-card layout.
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            job_cards = soup.find_all("div", class_="job-search-card")
            if not job_cards:
                job_cards = soup.find_all("li", class_="result-card")

            for card in job_cards[:limit]:
                job = self._parse_job_card(card)
                if job:
                    jobs.append(job)

        except Exception as e:
            print(f"Error fetching from LinkedIn: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from LinkedIn HTML (legacy + current markup)."""
        try:
            # Extract title
            title_elem = self._find_first(
                card,
                "h3",
                "base-search-card__title",
                "result-card__title",
            )
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = self._find_first(
                card,
                "h4",
                "base-search-card__subtitle",
                "result-card__company-name",
            )
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = self._find_first(
                card,
                "a",
                "base-card__full-link",
                "result-card__full-card-link",
            )
            url = link_elem["href"] if link_elem else None

            # Extract location
            location_elem = self._find_first(
                card,
                "span",
                "job-search-card__location",
                "job-result__location",
            )
            location = location_elem.get_text(strip=True) if location_elem else None

            # Extract date
            date_elem = self._find_first(
                card,
                "time",
                "job-search-card__listdate",
                "result-card__listed-date",
            )
            posted_at = None
            if date_elem and date_elem.get("datetime"):
                posted_at = datetime.fromisoformat(
                    date_elem["datetime"].replace("Z", "+00:00"),
                )

            # Extract description (present on the legacy layout only)
            desc_elem = self._find_first(
                card,
                "p",
                "base-search-card__snippet",
                "result-card__snippet",
            )
            description = desc_elem.get_text(strip=True) if desc_elem else None

            if not title or not url:
                return None

            raw_data = {}
            entity_urn = card.get("data-entity-urn")
            if entity_urn:
                raw_data["job_id"] = entity_urn.rsplit(":", 1)[-1]

            return RawJob(
                title=title,
                company=company,
                url=url,
                description=description,
                location=location,
                posted_at=posted_at,
                source=self.source_name,
                tags=self._extract_tags(title, description),
                raw_data=raw_data or None,
            )

        except Exception:
            return None

    def _extract_tags(self, title: str, description: str | None) -> list[str]:
        """Extract skill tags from job data."""
        tags = []
        text = f"{title} {description or ''}".lower()

        skill_keywords = {
            "python": "python",
            "javascript": "javascript",
            "react": "react",
            "node": "nodejs",
            "java": "java",
            "sql": "sql",
            "aws": "aws",
            "docker": "docker",
            "kubernetes": "kubernetes",
            "remote": "remote",
        }

        for keyword, tag in skill_keywords.items():
            if keyword in text:
                tags.append(tag)

        return tags
