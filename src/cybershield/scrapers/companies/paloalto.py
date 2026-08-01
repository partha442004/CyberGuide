"""
Palo Alto Networks Careers Scraper

Scrapes cybersecurity jobs from Palo Alto Networks' Workday-powered career page.
"""

from typing import Optional

from cybershield.scrapers.base import ScraperConfig
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper

__all__ = ["PaloAltoScraper"]


class PaloAltoScraper(BaseWorkdayScraper):
    """Scraper for Palo Alto Networks Careers (Workday ATS)."""

    CAREER_URL = "https://www.paloaltonetworks.com/careers"
    API_URL = "https://paloaltonetworks.wd1.myworkdayjobs.com/wday/cxs/paloaltonetworks/Careers/jobs"
    COMPANY_SLUG = "Careers"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "cloud security",
        "network security",
        "SOC",
        "threat intelligence",
        "incident response",
        "penetration testing",
        "vulnerability",
        "firewall",
        "Prisma",
        "Cortex",
        "WildFire",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_paloalto",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Palo Alto Networks",
            career_url=self.CAREER_URL,
            config=config,
        )
