"""
CyberShield Scrapers Package

Scrapers organized by region and source type.
"""

from .base import BaseScraper
from .registry import ScraperRegistry

__all__ = ["BaseScraper", "ScraperRegistry"]
