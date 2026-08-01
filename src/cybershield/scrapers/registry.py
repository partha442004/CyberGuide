"""
Scraper Registry

Central registry for managing and orchestrating all scrapers.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class ScraperRegistry:
    """
    Central registry for all scrapers.

    Features:
    - Register/unregister scrapers
    - Run individual or all scrapers
    - Parallel execution with concurrency control
    - Statistics and monitoring
    """

    _scrapers: Dict[str, Type[BaseScraper]] = {}
    _instances: Dict[str, BaseScraper] = {}

    @classmethod
    def register(cls, name: str, scraper_class: Type[BaseScraper]) -> None:
        """Register a scraper class."""
        cls._scrapers[name] = scraper_class
        logger.info(f"Registered scraper: {name}")

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a scraper."""
        cls._scrapers.pop(name, None)
        cls._instances.pop(name, None)

    @classmethod
    def get_scraper(cls, name: str, config: Optional[ScraperConfig] = None) -> BaseScraper:
        """Get a scraper instance by name."""
        if name not in cls._scrapers:
            raise ValueError(f"Scraper '{name}' not registered")

        if name not in cls._instances or config:
            cls._instances[name] = cls._scrapers[name](config)
        return cls._instances[name]

    @classmethod
    def list_scrapers(cls) -> List[str]:
        """List all registered scraper names."""
        return list(cls._scrapers.keys())

    @classmethod
    def get_scrapers_by_region(cls, region: str) -> List[str]:
        """Get scrapers for a specific region."""
        region_map = {
            "india": ["naukri", "internshala", "unstop", "freshersworld"],
            "usa": ["indeed", "linkedin"],
            "global": ["remoteok", "hackernews", "rss_feeds"],
            "companies": ["company_microsoft", "company_google", "company_amazon", "company_cisco"],
        }
        return region_map.get(region.lower(), [])

    @classmethod
    async def run_scraper(
        cls,
        name: str,
        config: Optional[ScraperConfig] = None,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Run a single scraper."""
        scraper = cls.get_scraper(name, config)
        return await scraper.run(**kwargs)

    @classmethod
    async def run_region(
        cls,
        region: str,
        max_concurrent: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Run all scrapers for a region in parallel."""
        scraper_names = cls.get_scrapers_by_region(region)
        if not scraper_names:
            logger.warning(f"No scrapers found for region: {region}")
            return []

        logger.info(f"Running {len(scraper_names)} scrapers for region: {region}")

        semaphore = asyncio.Semaphore(max_concurrent)
        all_jobs: List[ScrapedJob] = []

        async def run_with_semaphore(name: str):
            async with semaphore:
                try:
                    jobs = await cls.run_scraper(name, **kwargs)
                    all_jobs.extend(jobs)
                except Exception as e:
                    logger.error(f"Error running scraper {name}: {e}")

        tasks = [run_with_semaphore(name) for name in scraper_names]
        await asyncio.gather(*tasks)

        logger.info(f"Region {region} completed: {len(all_jobs)} jobs")
        return all_jobs

    @classmethod
    async def run_all(
        cls,
        regions: Optional[List[str]] = None,
        max_concurrent: int = 5,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Run all scrapers across specified regions."""
        regions = regions or ["india", "usa", "global", "companies"]
        all_jobs: List[ScrapedJob] = []

        for region in regions:
            jobs = await cls.run_region(region, max_concurrent=max_concurrent, **kwargs)
            all_jobs.extend(jobs)

        logger.info(f"All scrapers completed: {len(all_jobs)} total jobs")
        return all_jobs

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get statistics from all scraper instances."""
        stats = {}
        for name, instance in cls._instances.items():
            stats[name] = instance.get_stats()
        return stats


def _register_all_scrapers():
    """Register all built-in scrapers."""
    # India scrapers
    from cybershield.scrapers.india.freshersworld import FreshersworldScraper
    from cybershield.scrapers.india.internshala import InternshalaScraper
    from cybershield.scrapers.india.naukri import NaukriScraper
    from cybershield.scrapers.india.unstop import UnstopScraper

    ScraperRegistry.register("naukri", NaukriScraper)
    ScraperRegistry.register("internshala", InternshalaScraper)
    ScraperRegistry.register("unstop", UnstopScraper)
    ScraperRegistry.register("freshersworld", FreshersworldScraper)

    # USA scrapers
    from cybershield.scrapers.usa.indeed import IndeedScraper
    from cybershield.scrapers.usa.linkedin import LinkedInScraper

    ScraperRegistry.register("indeed", IndeedScraper)
    ScraperRegistry.register("linkedin", LinkedInScraper)

    # Global scrapers
    from cybershield.scrapers.worldwide.hackernews import HackerNewsScraper
    from cybershield.scrapers.worldwide.remoteok import RemoteOKScraper
    from cybershield.scrapers.worldwide.rss_feeds import RSSFeedScraper

    ScraperRegistry.register("remoteok", RemoteOKScraper)
    ScraperRegistry.register("hackernews", HackerNewsScraper)
    ScraperRegistry.register("rss_feeds", RSSFeedScraper)

    # Company scrapers
    from cybershield.scrapers.companies.amazon import AmazonScraper
    from cybershield.scrapers.companies.checkpoint import CheckPointScraper
    from cybershield.scrapers.companies.cisco import CiscoScraper
    from cybershield.scrapers.companies.crowdstrike import CrowdStrikeScraper
    from cybershield.scrapers.companies.fortinet import FortinetScraper
    from cybershield.scrapers.companies.google import GoogleScraper
    from cybershield.scrapers.companies.mcafee import McAfeeScraper
    from cybershield.scrapers.companies.microsoft import MicrosoftScraper
    from cybershield.scrapers.companies.paloalto import PaloAltoScraper
    from cybershield.scrapers.companies.symantec import SymantecScraper
    from cybershield.scrapers.companies.trendmicro import TrendMicroScraper

    ScraperRegistry.register("company_microsoft", MicrosoftScraper)
    ScraperRegistry.register("company_google", GoogleScraper)
    ScraperRegistry.register("company_amazon", AmazonScraper)
    ScraperRegistry.register("company_cisco", CiscoScraper)
    ScraperRegistry.register("company_crowdstrike", CrowdStrikeScraper)
    ScraperRegistry.register("company_paloalto", PaloAltoScraper)
    ScraperRegistry.register("company_fortinet", FortinetScraper)
    ScraperRegistry.register("company_checkpoint", CheckPointScraper)
    ScraperRegistry.register("company_symantec", SymantecScraper)
    ScraperRegistry.register("company_mcafee", McAfeeScraper)
    ScraperRegistry.register("company_trendmicro", TrendMicroScraper)

    logger.info(f"Registered {len(ScraperRegistry.list_scrapers())} scrapers")


# Auto-register all scrapers on import
_register_all_scrapers()
