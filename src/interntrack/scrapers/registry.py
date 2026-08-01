"""
Scraper registry for managing multiple job sources.
"""

from interntrack.scrapers.base import BaseScraper


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
        """Fetch jobs from all or specified sources."""

        all_jobs = []
        scrapers = self.get_all()

        if sources:
            scrapers = [s for s in scrapers if s.source_name in sources]

        for scraper in scrapers:
            try:
                jobs = await scraper.fetch(query, location, limit)
                all_jobs.extend([job.to_dict() for job in jobs])
            except Exception as e:
                print(f"Error fetching from {scraper.source_name}: {e}")
                continue

        return all_jobs

    async def close_all(self) -> None:
        """Close all scraper clients."""
        for scraper in self.get_all():
            await scraper.close()


def get_default_registry() -> ScraperRegistry:
    """Create default scraper registry with all scrapers."""
    registry = ScraperRegistry()

    # Import and register scrapers
    from interntrack.scrapers.glassdoor import GlassdoorScraper
    from interntrack.scrapers.hackernews import HackerNewsScraper
    from interntrack.scrapers.indeed import IndeedScraper
    from interntrack.scrapers.linkedin import LinkedInScraper
    from interntrack.scrapers.remoteok import RemoteOKScraper
    from interntrack.scrapers.rss_feeds import RSSFeedScraper

    registry.register(HackerNewsScraper())
    registry.register(RemoteOKScraper())
    registry.register(RSSFeedScraper())
    registry.register(LinkedInScraper())
    registry.register(IndeedScraper())
    registry.register(GlassdoorScraper())

    return registry
