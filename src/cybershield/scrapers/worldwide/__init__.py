"""
Global Scrapers Package

Scrapers for worldwide job sources.
"""

from .hackernews import HackerNewsScraper
from .remoteok import RemoteOKScraper
from .rss_feeds import RSSFeedScraper

__all__ = [
    "RemoteOKScraper",
    "HackerNewsScraper",
    "RSSFeedScraper",
]
