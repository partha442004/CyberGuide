"""
Direct Internshala scraper — fetches from internshala.com/internships.
No API key needed; parses the public HTML listing page.
"""

import logging
import re
from urllib.parse import urljoin

from interntrack.scrapers.base import BaseScraper, RawJob

logger = logging.getLogger(__name__)


class InternshalaDirectScraper(BaseScraper):
    """Scrape internshala.com public internship listings."""

    BASE_URL = "https://internshala.com"

    @property
    def source_name(self) -> str:
        return "internshala"

    async def fetch(
        self, query: str, location: str | None = None, limit: int = 50
    ) -> list[RawJob]:
        import httpx

        search_url = f"{self.BASE_URL}/internships/keyword/{query.replace(' ', '-')}/"
        if location:
            search_url = f"{self.BASE_URL}/internships/{location.lower().replace(' ', '-')}/{query.replace(' ', '-')}/"

        jobs: list[RawJob] = []
        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            ) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    logger.warning(
                        "Internshala returned %d for %s", resp.status_code, search_url
                    )
                    return jobs

                html = resp.text
                # Extract job cards from the page
                card_pattern = re.compile(
                    r'<div[^>]*class="[^"]*individual_internship[^"]*"[^>]*>.*?</div>\s*</div>\s*</div>',
                    re.DOTALL,
                )
                cards = card_pattern.findall(html)

                if not cards:
                    # Fallback: try to find title links
                    title_pattern = re.compile(
                        r'<a[^>]*href="(/internship/[^"]+)"[^>]*>\s*<h3[^>]*>([^<]+)</h3>',
                        re.DOTALL,
                    )
                    matches = title_pattern.findall(html)
                    for href, title in matches[:limit]:
                        company_match = re.search(
                            r"company_name[^>]*>([^<]+)",
                            html[html.find(href) : html.find(href) + 500]
                            if href in html
                            else "",
                        )
                        jobs.append(
                            RawJob(
                                title=title.strip(),
                                company=company_match.group(1).strip()
                                if company_match
                                else "Unknown",
                                url=urljoin(self.BASE_URL, href),
                                source=self.source_name,
                                description=title.strip(),
                            )
                        )
                else:
                    for card in cards[:limit]:
                        title_m = re.search(r"<h3[^>]*>([^<]+)</h3>", card)
                        company_m = re.search(r"company_name[^>]*>([^<]+)", card)
                        link_m = re.search(r'href="(/internship/[^"]+)"', card)
                        if title_m:
                            jobs.append(
                                RawJob(
                                    title=title_m.group(1).strip(),
                                    company=company_m.group(1).strip()
                                    if company_m
                                    else "Unknown",
                                    url=urljoin(self.BASE_URL, link_m.group(1))
                                    if link_m
                                    else search_url,
                                    source=self.source_name,
                                    description=title_m.group(1).strip(),
                                )
                            )

        except Exception as e:
            logger.warning("Internshala scrape failed: %s", e)

        return jobs[:limit]
