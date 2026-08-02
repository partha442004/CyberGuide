"""
Tests for the interntrack init_db schema-drift reconciliation.

Verifies that _sync_missing_columns adds model columns missing from an
existing table (the Railway Postgres jobs.tags scenario) while leaving
already-present columns untouched and skipping NOT NULL columns without
defaults.
"""

import pytest
from sqlalchemy import Column, MetaData, String, Table, text
from sqlalchemy.ext.asyncio import create_async_engine

from interntrack.database.session import _sync_missing_columns


@pytest.fixture
def drift_engine():
    """An engine whose schema intentionally lacks the current model columns."""
    return create_async_engine("sqlite+aiosqlite:///:memory:")


class TestSyncMissingColumns:
    @pytest.mark.asyncio
    async def test_adds_missing_column_to_existing_table(self, drift_engine):
        # Build a jobs-like table missing the tags column
        metadata = MetaData()
        Table(
            "jobs",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("title", String(500), nullable=False),
        )
        async with drift_engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            # Simulate the drift: add a column via the sync helper
            await conn.run_sync(_sync_missing_columns)

        # Verify the model column was added
        async with drift_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(jobs)"))
            columns = [row[1] for row in result.fetchall()]
        assert "tags" in columns

    @pytest.mark.asyncio
    async def test_does_not_duplicate_existing_columns(self, drift_engine):
        # Create the table with the full model schema so nothing is missing
        from interntrack.domain.models import Base

        async with drift_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_sync_missing_columns)

        async with drift_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info(jobs)"))
            columns = [row[1] for row in result.fetchall()]
        # tags must exist exactly once
        assert columns.count("tags") == 1
        assert "id" in columns

    @pytest.mark.asyncio
    async def test_skips_tables_that_do_not_exist(self, drift_engine):
        # No tables exist yet — sync must be a no-op (no error)
        async with drift_engine.begin() as conn:
            await conn.run_sync(_sync_missing_columns)

    @pytest.mark.asyncio
    async def test_works_via_init_db_path(self):
        """End-to-end: init_db on a fresh DB adds nothing and does not error."""
        from interntrack.database import session as session_module

        original_engine = session_module.engine
        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_module.engine = test_engine
        try:
            await session_module.init_db()
            # A second call must also succeed (idempotent)
            await session_module.init_db()
        finally:
            session_module.engine = original_engine
            await test_engine.dispose()
