"""
India Scrapers Package

Scrapers for India-based job sources.
"""

from .freshersworld import FreshersworldScraper
from .internshala import InternshalaScraper
from .naukri import NaukriScraper
from .unstop import UnstopScraper

__all__ = [
    "NaukriScraper",
    "InternshalaScraper",
    "UnstopScraper",
    "FreshersworldScraper",
]
