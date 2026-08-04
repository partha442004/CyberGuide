"""
Backfill job skills for existing jobs.

The live Neon ``jobs`` table was created by the interntrack model (which
stores skills in ``tags``) before the cybershield model added the
``required_skills`` / ``preferred_skills`` columns. This one-off script
extracts skills from each job's title + description + tags using the same
word-boundary matcher the scrapers use, and writes them into
``required_skills`` (deduplicated).

Uses raw SQL so it stays compatible with the live table shape (the cybershield
ORM model declares columns/relationships that do not match the interntrack
schema, so ORM flush fails).

Usage:
    CYBERSHIELD_DATABASE_URL=<neon url> python -m interntrack.scripts.backfill_job_skills
"""  # noqa: E501

import asyncio
import json
import sys

from sqlalchemy import text

sys.path.insert(0, "src")


def _extract_skills_text(text: str) -> list[str]:
    """Extract skills using the scraper's word-boundary matcher."""
    from cybershield.scrapers.base import extract_skills_from_text

    return extract_skills_from_text(text)


async def backfill(limit: int | None = None) -> int:
    """Enrich every job that lacks required_skills with extracted skills."""
    from cybershield.database.session import get_engine, init_db

    await init_db()

    engine = get_engine()
    updated = 0
    async with engine.connect() as conn:
        sql = (
            "SELECT id, title, description, tags FROM jobs "
            "WHERE required_skills IS NULL "
            "OR required_skills::text IN ('[]', 'null', '') "
            "LIMIT :limit"
        )
        rows = (
            (await conn.execute(text(sql), {"limit": int(limit or 1000000)}))
            .mappings()
            .all()
        )
        print(f"Found {len(rows)} jobs missing skills")

        for row in rows:
            tags = " ".join(row["tags"] or [])
            text_blob = " ".join(
                x for x in (row["title"] or "", row["description"] or "", tags) if x
            )
            skills = _extract_skills_text(text_blob)
            if skills:
                payload = json.dumps(skills)
                await conn.execute(
                    text("UPDATE jobs SET required_skills = :skills WHERE id = :id"),
                    {"skills": payload, "id": row["id"]},
                )
                updated += 1
                print(
                    f"  + {str(row['id'])[:8]} {(row['title'] or '')[:40]!r}: "
                    f"{', '.join(skills[:8])}"
                )

        if updated:
            await conn.commit()
    return updated


if __name__ == "__main__":
    total = asyncio.run(backfill(limit=None))
    print(f"\nBackfilled {total} jobs with skills.")
