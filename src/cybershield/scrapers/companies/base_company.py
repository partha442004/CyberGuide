"""
Base Company Scraper

Base class for scraping individual company career pages.
"""

import logging
from abc import abstractmethod
from typing import List, Optional

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class BaseCompanyScraper(BaseScraper):
    """
    Base class for company-specific scrapers.

    All company scrapers should inherit from this class
    and implement the scrape() method.
    """

    def __init__(
        self,
        company_name: str,
        career_url: str,
        config: Optional[ScraperConfig] = None,
    ):
        self.company_name = company_name
        self.career_url = career_url

        config = config or ScraperConfig(
            name=f"company_{company_name.lower().replace(' ', '_')}",
            base_url=career_url,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(config)

    def _tag_job(self, job: ScrapedJob) -> ScrapedJob:
        """Tag job with company info and source."""
        job.company_name = self.company_name
        job.source = f"company_{self.company_name.lower().replace(' ', '_')}"
        return job

    def _is_security_role(self, job: ScrapedJob) -> bool:
        """Check if job is security-related."""
        security_keywords = [
            "security",
            "cyber",
            "soc",
            "infosec",
            "penetration",
            "vulnerability",
            "threat",
            "incident",
            "forensic",
            "malware",
            "devsecops",
            "compliance",
            "governance",
            "risk",
        ]

        title_lower = (job.title or "").lower()
        desc_lower = (job.description or "").lower()

        return any(kw in title_lower or kw in desc_lower for kw in security_keywords)

    @abstractmethod
    async def scrape(self, **kwargs) -> List[ScrapedJob]:
        """Scrape company career page."""
        pass
