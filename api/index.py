"""
Vercel serverless entrypoint for CyberGuide / InternTrack.

Vercel's Python runtime expects a file at ``api/index.py`` with a top-level
``app`` variable. This module re-exports the FastAPI application from the
main package.

The database engine is automatically configured with ``NullPool`` when the
``DATABASE_URL`` starts with ``postgresql`` (see ``session.py``), making it
serverless-safe. The ``init_db()`` call on every cold start is idempotent
because ``create_all`` only creates tables that don't exist yet, and
``_sync_missing_columns`` only adds nullable/defaulted columns — both are
no-ops on an already-synced schema.
"""

import os
import sys

# Ensure the src/ directory is on the path so ``import interntrack`` works
# when Vercel runs the function from the project root.
_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# ── Override defaults before the config module is read ────────────────────
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")  # No Redis on Vercel free

# ── Import the FastAPI app ────────────────────────────────────────────────
# This triggers the module-level engine creation in session.py, which uses
# NullPool automatically for Postgres URLs.
from interntrack.database.session import init_db
from interntrack.main import app

# ── Initialize database on cold start ─────────────────────────────────────
# This runs once when the serverless function cold-starts. It's a no-op if
# all tables and columns already exist.
import asyncio

try:
    asyncio.get_event_loop().run_until_complete(init_db())
except RuntimeError:
    # Already running in an event loop (Vercel's runtime handles this)
    pass

# The `app` variable is exported from interntrack.main and discovered
# by Vercel's ASGI runtime.
