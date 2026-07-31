"""Scraper infrastructure for job discovery."""

from interntrack.scrapers.base import BaseScraper
from interntrack.scrapers.registry import ScraperRegistry

__all__ = ["BaseScraper", "ScraperRegistry"]
