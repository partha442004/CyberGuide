"""
Deduplication engine for identifying and removing duplicate job postings.
"""

import hashlib
import re
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.models import Job
from interntrack.repositories.job_repository import JobRepository


class DeduplicationEngine:
    """Engine for deduplicating job postings."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)

    async def filter_unique(self, jobs: list[dict]) -> list[dict]:
        """Filter out duplicate jobs from a list."""
        unique_jobs = []
        seen_hashes = set()

        for job_data in jobs:
            job_hash = self._compute_hash(job_data)

            # Check against seen hashes in this batch
            if job_hash in seen_hashes:
                continue

            # Check against existing jobs in database
            existing = await self._find_existing(job_data)
            if existing:
                continue

            seen_hashes.add(job_hash)
            unique_jobs.append(job_data)

        return unique_jobs

    async def _find_existing(self, job_data: dict) -> Job | None:
        """Find existing job that matches the given data."""
        url = job_data.get("url")
        if url:
            existing = await self.job_repo.get_by_url(url)
            if existing:
                return existing

        # Check by title + company similarity
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        source = job_data.get("source", "unknown")

        if title and company:
            existing = await self.job_repo.find_duplicate(title, company, source)
            if existing:
                return existing

        return None

    def _compute_hash(self, job_data: dict) -> str:
        """Compute hash for job data."""
        key_fields = [
            job_data.get("title", "").lower().strip(),
            job_data.get("company", "").lower().strip(),
            job_data.get("url", "").lower().strip(),
        ]
        key_string = "|".join(key_fields)
        return hashlib.md5(key_string.encode()).hexdigest()

    def calculate_similarity(self, job1: dict, job2: dict) -> float:
        """Calculate similarity score between two jobs."""
        scores = []

        # Title similarity
        title1 = job1.get("title", "").lower()
        title2 = job2.get("title", "").lower()
        scores.append(SequenceMatcher(None, title1, title2).ratio())

        # Company similarity
        company1 = job1.get("company", "").lower()
        company2 = job2.get("company", "").lower()
        scores.append(SequenceMatcher(None, company1, company2).ratio())

        # URL similarity
        url1 = self._normalize_url(job1.get("url", ""))
        url2 = self._normalize_url(job2.get("url", ""))
        scores.append(SequenceMatcher(None, url1, url2).ratio())

        return sum(scores) / len(scores)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        url = url.lower()
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        url = url.rstrip('/')
        return url

    async def find_duplicates_in_database(
        self, threshold: float = 0.85,
    ) -> list[tuple[Job, Job]]:
        """Find potential duplicates in the database."""
        from sqlalchemy import select

        query = select(Job).where(Job.is_active)
        result = await self.session.execute(query)
        all_jobs = list(result.scalars().all())

        duplicates = []
        seen_pairs = set()

        for i, job1 in enumerate(all_jobs):
            for job2 in all_jobs[i + 1:]:
                pair_key = tuple(sorted([job1.id, job2.id]))
                if pair_key in seen_pairs:
                    continue

                job1_dict = {
                    "title": job1.title,
                    "company": job1.company,
                    "url": job1.url,
                }
                job2_dict = {
                    "title": job2.title,
                    "company": job2.company,
                    "url": job2.url,
                }

                similarity = self.calculate_similarity(job1_dict, job2_dict)
                if similarity >= threshold:
                    duplicates.append((job1, job2))
                    seen_pairs.add(pair_key)

        return duplicates
