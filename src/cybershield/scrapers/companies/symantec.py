"""
Symantec (Broadcom) Careers Scraper

Scrapes cybersecurity jobs from Broadcom/Symantec's Workday-powered career page.
Symantec was acquired by Broadcom in 2019 and operates under Broadcom's unified Workday ATS.
"""

from typing import List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper


__all__ = ["SymantecScraper"]


class SymantecScraper(BaseWorkdayScraper):
    """Scraper for Broadcom/Symantec Careers (Workday ATS)."""

    CAREER_URL = "https://broadcom.wd1.myworkdayjobs.com/External_Career"
    API_URL = "https://broadcom.wd1.myworkdayjobs.com/wday/cxs/broadcom/External_Career/jobs"
    COMPANY_SLUG = "External_Career"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "endpoint security",
        "threat intelligence",
        "incident response",
        "malware analysis",
        "SOC",
        "penetration testing",
        "vulnerability",
        "data loss prevention",
        "DLP",
        "encryption",
        "identity management",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_symantec",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Broadcom Symantec",
            career_url=self.CAREER_URL,
            config=config,
        )
