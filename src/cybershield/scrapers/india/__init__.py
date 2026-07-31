"""
India Scrapers Package

Scrapers for India-based job sources.
"""

from .naukri import NaukriScraper
from .internshala import InternshalaScraper
from .unstop import UnstopScraper
from .freshersworld import FreshersworldScraper

__all__ = [
    "NaukriScraper",
    "InternshalaScraper",
    "UnstopScraper",
    "FreshersworldScraper",
]
