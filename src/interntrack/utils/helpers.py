"""
General helper functions.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a *naive* datetime.

    The DB columns are plain ``timestamp without time zone`` on PostgreSQL
    (``Column(DateTime, ...)``), so asyncpg rejects offset-aware values.
    Storing naive UTC keeps SQLite (tests) and PostgreSQL (production)
    consistent without a migration.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Coerce a datetime to naive UTC for Postgres ``timestamp`` columns.

    Scrapers and API clients can hand us offset-aware datetimes (e.g. parsed
    from ISO-8601 with ``+00:00``); asyncpg rejects those when binding to a
    ``timestamp without time zone`` column with ``can't subtract
    offset-naive and offset-aware datetimes``. This normalizes them to naive
    UTC (the same convention as :func:`utcnow`) without a migration.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime to string."""
    if dt:
        return dt.strftime(fmt)
    return "N/A"


def format_currency(amount: int | None, currency: str = "USD") -> str:
    """Format currency amount."""
    if amount is None:
        return "N/A"
    return f"${amount:,.2f} {currency}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def slugify(text: str) -> str:
    """Convert text to slug."""
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def generate_id() -> str:
    """Generate a unique ID."""
    from uuid import uuid4

    return str(uuid4())
