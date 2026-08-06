"""
Company watchlist API schemas.
"""

from pydantic import BaseModel


class CompanyWatchlistCreate(BaseModel):
    """Add a company to a user's watchlist."""

    user_id: str
    company: str
    notes: str | None = None


class CompanyWatchlistItem(BaseModel):
    """A watched company with its current active-job count."""

    id: str
    company: str
    notes: str | None = None
    active_jobs: int = 0


class CompanyWatchlistList(BaseModel):
    """A user's company watchlist."""

    watchlist: list[CompanyWatchlistItem]
    total: int
