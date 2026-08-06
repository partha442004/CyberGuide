"""
Scraper registry for managing multiple job sources.
"""

import logging

from interntrack.metrics import business_metrics_store
from interntrack.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Bound concurrent source fetches so dozens of bridged scrapers cannot
# exhaust connections or exceed the serverless function timeout.
_MAX_CONCURRENT = 5


class ScraperRegistry:
    """Registry for managing scraper instances."""

    def __init__(self):
        self._scrapers: dict[str, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        """Register a scraper."""
        self._scrapers[scraper.source_name] = scraper

    def unregister(self, source_name: str) -> None:
        """Unregister a scraper."""
        if source_name in self._scrapers:
            del self._scrapers[source_name]

    def get(self, source_name: str) -> BaseScraper | None:
        """Get a scraper by source name."""
        return self._scrapers.get(source_name)

    def get_all(self) -> list[BaseScraper]:
        """Get all registered scrapers."""
        return list(self._scrapers.values())

    def list_sources(self) -> list[str]:
        """List all registered source names."""
        return list(self._scrapers.keys())

    async def fetch_all(
        self,
        query: str,
        location: str | None = None,
        sources: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch jobs from all or specified sources, concurrently.

        Sources run in parallel (bounded by :data:`_MAX_CONCURRENT`) so the
        wall-clock time is roughly the slowest source, not the sum of every
        source — important since the registry now bridges in many internship
        and company scrapers and Vercel serverless functions have a hard
        timeout.
        """

        all_jobs = []
        scrapers = self.get_all()

        if sources:
            scrapers = [s for s in scrapers if s.source_name in sources]

        import asyncio

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def fetch_one(scraper: BaseScraper) -> list[dict]:
            async with semaphore:
                try:
                    jobs = await scraper.fetch(query, location, limit)
                    business_metrics_store.record_scraper_run(
                        scraper.source_name,
                        success=True,
                    )
                    return [job.to_dict() for job in jobs]
                except Exception as e:
                    business_metrics_store.record_scraper_run(
                        scraper.source_name,
                        success=False,
                    )
                    print(f"Error fetching from {scraper.source_name}: {e}")
                    return []

        results = await asyncio.gather(*(fetch_one(s) for s in scrapers))
        for chunk in results:
            all_jobs.extend(chunk)
        return all_jobs

    async def close_all(self) -> None:
        """Close all scraper clients."""
        for scraper in self.get_all():
            await scraper.close()


def get_default_registry() -> ScraperRegistry:
    """Create default scraper registry with all scrapers."""
    registry = ScraperRegistry()

    # Import and register scrapers. RemoteOK is intentionally NOT registered:
    # its public JSON API now returns non-job junk entries (site navigation
    # items and placeholder posts such as "Menu", "Basic", "Elite",
    # "Cleaning Assistant"), which polluted saved jobs. RemoteOK listings
    # still arrive via the remoteok RSS feed inside RSSFeedScraper.
    from interntrack.scrapers.angellist import AngelListScraper
    from interntrack.scrapers.glassdoor import GlassdoorScraper
    from interntrack.scrapers.glassdoor_india import GlassdoorIndiaScraper
    from interntrack.scrapers.google_jobs import GoogleJobsScraper
    from interntrack.scrapers.hackernews import HackerNewsScraper
    from interntrack.scrapers.hired import HiredScraper
    from interntrack.scrapers.indeed import IndeedScraper
    from interntrack.scrapers.indeed_api import IndeedAPIScraper
    from interntrack.scrapers.indeed_india import IndeedIndiaScraper
    from interntrack.scrapers.internshala_direct import InternshalaDirectScraper
    from interntrack.scrapers.linkedin import LinkedInScraper
    from interntrack.scrapers.linkedin_india import LinkedInIndiaScraper
    from interntrack.scrapers.linkedin_jobs_api import LinkedInJobsAPIScraper
    from interntrack.scrapers.rss_feeds import RSSFeedScraper
    from interntrack.scrapers.timesjobs import TimesJobsScraper
    from interntrack.scrapers.wellfound import WellfoundScraper

    registry.register(HackerNewsScraper())
    registry.register(RSSFeedScraper())
    registry.register(LinkedInScraper())
    registry.register(IndeedScraper())
    registry.register(GlassdoorScraper())
    registry.register(InternshalaDirectScraper())
    registry.register(WellfoundScraper())
    registry.register(GoogleJobsScraper())
    registry.register(IndeedIndiaScraper())
    registry.register(TimesJobsScraper())
    registry.register(LinkedInIndiaScraper())
    registry.register(GlassdoorIndiaScraper())
    registry.register(HiredScraper())
    registry.register(AngelListScraper())
    registry.register(LinkedInJobsAPIScraper())
    registry.register(IndeedAPIScraper())

    # Direct security-company Greenhouse career boards (no API key, never
    # blocks) - the most reliable source of real vendor security roles.
    try:
        from interntrack.scrapers.greenhouse import GreenhouseBoardScraper

        registry.register(GreenhouseBoardScraper())
    except Exception as e:
        logger.warning("Greenhouse board scraper unavailable: %s", e)

    # Indian internship boards and direct security-company career portals live
    # in the cybershield scraper library; adapt them into the same pipeline so
    # the daily discovery also covers internship sites and vendor career pages.
    try:
        from cybershield.scrapers.india.freshersworld import FreshersworldScraper
        from cybershield.scrapers.india.internshala import InternshalaScraper
        from cybershield.scrapers.india.naukri import NaukriScraper
        from cybershield.scrapers.india.unstop import UnstopScraper
        from interntrack.scrapers.cybershield_adapter import CybershieldScraperAdapter

        internship_sources = {
            "internshala": InternshalaScraper,
            "unstop": UnstopScraper,
            "naukri": NaukriScraper,
            "freshersworld": FreshersworldScraper,
        }
        for source, scraper_cls in internship_sources.items():
            try:
                registry.register(
                    CybershieldScraperAdapter(
                        source,
                        scraper_cls(),  # type: ignore[abstract]
                    ),
                )
            except Exception as e:
                logger.warning("Skipping internship scraper %s: %s", source, e)

        from cybershield.scrapers.companies.checkpoint import CheckPointScraper
        from cybershield.scrapers.companies.crowdstrike import CrowdStrikeScraper
        from cybershield.scrapers.companies.fortinet import FortinetScraper
        from cybershield.scrapers.companies.mcafee import McAfeeScraper
        from cybershield.scrapers.companies.paloalto import PaloAltoScraper
        from cybershield.scrapers.companies.symantec import SymantecScraper
        from cybershield.scrapers.companies.trendmicro import TrendMicroScraper

        company_sources = {
            "crowdstrike": CrowdStrikeScraper,
            "paloalto": PaloAltoScraper,
            "fortinet": FortinetScraper,
            "checkpoint": CheckPointScraper,
            "symantec": SymantecScraper,
            "mcafee": McAfeeScraper,
            "trendmicro": TrendMicroScraper,
        }
        for source, scraper_cls in company_sources.items():
            try:
                registry.register(
                    CybershieldScraperAdapter(
                        source,
                        scraper_cls(),  # type: ignore[abstract]
                    ),
                )
            except Exception as e:
                logger.warning("Skipping company scraper %s: %s", source, e)
    except Exception as e:
        # The cybershield library is optional at runtime; core sources above
        # always keep the pipeline working even if it is unavailable.
        logger.warning("Cybershield scraper library unavailable: %s", e)

    return registry
