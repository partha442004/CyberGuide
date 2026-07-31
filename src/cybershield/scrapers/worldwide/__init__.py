"""
Global Scrapers Package

Scrapers for worldwide job sources.
"""

from .remoteok import RemoteOKScraper
from .hackernews import HackerNewsScraper
from .rss_feeds import RSSFeedScraper

__all__ = [
    "RemoteOKScraper",
    "HackerNewsScraper",
    "RSSFeedScraper",
]
