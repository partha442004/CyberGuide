"""
Shared utility helpers for CyberGuide (cybershield).

DB columns are plain ``timestamp without time zone`` on PostgreSQL
(``Column(DateTime, ...)``), so asyncpg rejects offset-aware values on both
queries and inserts. All DB-facing code must use naive UTC values; this module
provides a single helper for that.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a *naive* datetime (DB-compatible)."""
    return datetime.now(UTC).replace(tzinfo=None)
