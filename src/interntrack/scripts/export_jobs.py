"""
Export jobs to CSV format.
"""

import asyncio
import csv
from pathlib import Path

from interntrack.database.session import get_db_session, init_db
from interntrack.domain.models import Job


async def export_jobs(
    output_file: str = "jobs_export.csv",
    format: str = "csv",
    limit: int | None = None,
    source: str | None = None,
) -> str:
    """Export jobs to CSV or JSON file."""
    await init_db()

    async with get_db_session() as session:
        from sqlalchemy import select

        query = select(Job).where(Job.is_active)

        if source:
            from interntrack.domain.enums import JobSource
            query = query.where(Job.source == JobSource(source))

        query = query.order_by(Job.created_at.desc())

        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        jobs = list(result.scalars().all())

        if not jobs:
            print("No jobs found to export.")
            return ""

        output_path = Path(output_file)

        if format.lower() == "csv":
            _export_csv(jobs, output_path)
        elif format.lower() == "json":
            _export_json(jobs, output_path)
        else:
            print(f"Unsupported format: {format}")
            return ""

        print(f"✅ Exported {len(jobs)} jobs to {output_path}")
        return str(output_path)


def _export_csv(jobs: list[Job], output_path: Path):
    """Export jobs to CSV format."""
    headers = [
        "id",
        "title",
        "company",
        "location",
        "description",
        "url",
        "source",
        "job_type",
        "experience_level",
        "salary_min",
        "salary_max",
        "salary_currency",
        "is_remote",
        "posted_at",
        "expires_at",
        "is_active",
        "tags",
        "created_at",
        "updated_at",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for job in jobs:
            row = {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location or "",
                "description": job.description or "",
                "url": job.url,
                "source": job.source.value if job.source else "",
                "job_type": job.job_type.value if job.job_type else "",
                "experience_level": job.experience_level.value if job.experience_level else "",
                "salary_min": job.salary_min or "",
                "salary_max": job.salary_max or "",
                "salary_currency": job.salary_currency or "USD",
                "is_remote": job.is_remote,
                "posted_at": job.posted_at.isoformat() if job.posted_at else "",
                "expires_at": job.expires_at.isoformat() if job.expires_at else "",
                "is_active": job.is_active,
                "tags": ",".join(job.tags) if job.tags else "",
                "created_at": job.created_at.isoformat() if job.created_at else "",
                "updated_at": job.updated_at.isoformat() if job.updated_at else "",
            }
            writer.writerow(row)


def _export_json(jobs: list[Job], output_path: Path):
    """Export jobs to JSON format."""
    import json

    data = []
    for job in jobs:
        data.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "url": job.url,
            "source": job.source.value if job.source else None,
            "job_type": job.job_type.value if job.job_type else None,
            "experience_level": job.experience_level.value if job.experience_level else None,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "is_remote": job.is_remote,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "expires_at": job.expires_at.isoformat() if job.expires_at else None,
            "is_active": job.is_active,
            "tags": job.tags or [],
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Export jobs from InternTrack database")
    parser.add_argument(
        "-o", "--output",
        default="jobs_export.csv",
        help="Output file path (default: jobs_export.csv)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["csv", "json"],
        default="csv",
        help="Export format (default: csv)",
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=None,
        help="Limit number of jobs to export",
    )
    parser.add_argument(
        "-s", "--source",
        default=None,
        help="Filter by job source (e.g., linkedin, indeed, remote_ok)",
    )

    args = parser.parse_args()

    asyncio.run(export_jobs(
        output_file=args.output,
        format=args.format,
        limit=args.limit,
        source=args.source,
    ))


if __name__ == "__main__":
    main()
