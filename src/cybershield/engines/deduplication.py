"""
Deduplication Engine

Identifies and merges duplicate job listings using multiple strategies:
- URL normalization
- Hash-based matching
- Fuzzy string matching
- Semantic similarity
"""

import hashlib
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from cybershield.engines.base import BaseEngine, EngineResult

logger = logging.getLogger(__name__)


class DeduplicationEngine(BaseEngine):
    """
    Deduplication engine for job listings.

    Uses multiple strategies to identify duplicates:
    1. URL normalization and comparison
    2. Hash-based exact matching
    3. Fuzzy string matching for title/company
    4. Configurable similarity thresholds
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("deduplication", config)
        self.url_threshold = config.get("url_threshold", 0.95) if config else 0.95
        self.title_threshold = config.get("title_threshold", 0.85) if config else 0.85
        self.combined_threshold = config.get("combined_threshold", 0.80) if config else 0.80

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing tracking parameters and standardizing format."""
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            # Remove tracking parameters
            tracking_params = {
                "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
                "ref", "source", "from", "track", "click", "spm", "fbclid", "gclid",
            }
            cleaned_params = {k: v for k, v in params.items() if k.lower() not in tracking_params}

            # Normalize path
            path = parsed.path.rstrip("/")

            return urlunparse(parsed._replace(
                path=path,
                query=urlencode(cleaned_params, doseq=True),
                fragment=""
            ))
        except Exception:
            return url.lower().strip()

    def _generate_hash(self, *args: str) -> str:
        """Generate consistent hash from input strings."""
        content = "|".join(arg.lower().strip() for arg in args if arg)
        return hashlib.sha256(content.encode()).hexdigest()

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity ratio."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _extract_content_hash(self, job: Dict[str, Any]) -> str:
        """Extract content hash from job data."""
        title = job.get("title", "")
        company = job.get("company_name", "")
        location = job.get("location", "")
        return self._generate_hash(title, company, location)

    def _normalize_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize job data for comparison."""
        normalized = job.copy()
        normalized["normalized_url"] = self._normalize_url(job.get("url", ""))
        normalized["content_hash"] = self._extract_content_hash(job)
        normalized["title_lower"] = (job.get("title", "") or "").lower().strip()
        normalized["company_lower"] = (job.get("company_name", "") or "").lower().strip()
        return normalized

    def _are_urls_similar(self, url1: str, url2: str) -> Tuple[bool, float]:
        """Check if two URLs are similar (same job posting)."""
        norm1 = self._normalize_url(url1)
        norm2 = self._normalize_url(url2)

        if not norm1 or not norm2:
            return False, 0.0

        # Exact match after normalization
        if norm1 == norm2:
            return True, 1.0

        # Fuzzy match for slight variations
        similarity = self._calculate_similarity(norm1, norm2)
        return similarity >= self.url_threshold, similarity

    def _are_titles_similar(self, title1: str, title2: str) -> Tuple[bool, float]:
        """Check if two job titles are similar."""
        if not title1 or not title2:
            return False, 0.0

        similarity = self._calculate_similarity(title1, title2)
        return similarity >= self.title_threshold, similarity

    def _calculate_combined_score(
        self,
        url_similarity: float,
        title_similarity: float,
        company_match: bool,
    ) -> float:
        """Calculate combined similarity score."""
        # Weighted combination
        weights = {
            "url": 0.4,
            "title": 0.4,
            "company": 0.2,
        }

        score = (
            url_similarity * weights["url"] +
            title_similarity * weights["title"] +
            (1.0 if company_match else 0.0) * weights["company"]
        )
        return score

    def _select_canonical(
        self, jobs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Select the best job as canonical from a group of duplicates."""
        if len(jobs) == 1:
            return jobs[0]

        def score_job(job: Dict[str, Any]) -> int:
            score = 0

            # Prefer official company websites
            url = (job.get("url", "") or "").lower()
            company = (job.get("company_name", "") or "").lower()
            if company and company.replace(" ", "") in url:
                score += 50

            # Prefer jobs with more complete data
            fields = ["description", "salary_min", "deadline", "apply_url"]
            score += sum(10 for f in fields if job.get(f))

            # Prefer earlier posting dates
            if job.get("posting_date"):
                score += 20

            # Prefer jobs from official sources
            source = (job.get("source", "") or "").lower()
            if "company_" in source:
                score += 30

            return score

        return max(jobs, key=score_job)

    async def process(
        self,
        jobs: List[Dict[str, Any]],
        **kwargs,
    ) -> EngineResult:
        """
        Process a list of jobs and identify duplicates.

        Args:
            jobs: List of job dictionaries

        Returns:
            EngineResult with duplicate groups and canonical jobs
        """
        if not jobs:
            return self._create_result(True, data={"groups": [], "unique_count": 0})

        # Normalize all jobs
        normalized_jobs = [self._normalize_job(job) for job in jobs]

        # Build groups of potential duplicates
        groups: List[List[int]] = []
        assigned: set = set()

        for i, job_i in enumerate(normalized_jobs):
            if i in assigned:
                continue

            group = [i]
            assigned.add(i)

            for j, job_j in enumerate(normalized_jobs):
                if j in assigned or j <= i:
                    continue

                # Check URL similarity
                url_match, url_sim = self._are_urls_similar(
                    job_i.get("url", ""), job_j.get("url", "")
                )

                # Check title similarity
                title_match, title_sim = self._are_titles_similar(
                    job_i.get("title_lower", ""), job_j.get("title_lower", "")
                )

                # Check company match
                company_match = (
                    job_i.get("company_lower", "") == job_j.get("company_lower", "")
                    and job_i.get("company_lower", "") != ""
                )

                # Calculate combined score
                combined_score = self._calculate_combined_score(
                    url_sim, title_sim, company_match
                )

                # Determine if duplicate
                is_duplicate = (
                    (url_match and company_match) or
                    (combined_score >= self.combined_threshold) or
                    (title_match and company_match and url_sim > 0.5)
                )

                if is_duplicate:
                    group.append(j)
                    assigned.add(j)

            groups.append(group)

        # Select canonical jobs and build results
        duplicate_groups = []
        unique_jobs = []

        for group_indices in groups:
            group_jobs = [jobs[i] for i in group_indices]

            if len(group_jobs) > 1:
                canonical = self._select_canonical(group_jobs)
                duplicates = [jobs[i] for i in group_indices if jobs[i] is not canonical]

                duplicate_groups.append({
                    "canonical": canonical,
                    "duplicates": duplicates,
                    "duplicate_ids": [d.get("id") or d.get("source_id") for d in duplicates],
                    "group_size": len(group_jobs),
                })
            else:
                unique_jobs.append(group_jobs[0])

        return self._create_result(
            success=True,
            data={
                "duplicate_groups": duplicate_groups,
                "unique_jobs": unique_jobs,
                "unique_count": len(unique_jobs),
                "duplicate_groups_count": len(duplicate_groups),
                "total_duplicates": sum(g["group_size"] - 1 for g in duplicate_groups),
                "total_processed": len(jobs),
            }
        )

    async def find_duplicates(
        self,
        new_job: Dict[str, Any],
        existing_jobs: List[Dict[str, Any]],
    ) -> EngineResult:
        """Check if a new job duplicates any existing jobs."""
        result = await self.process([new_job] + existing_jobs)

        if not result.success:
            return result

        data = result.data
        # Check if the new job ended up in any duplicate group
        for group in data.get("duplicate_groups", []):
            if new_job in group.get("duplicates", []):
                return self._create_result(
                    success=True,
                    data={
                        "is_duplicate": True,
                        "canonical": group["canonical"],
                        "similarity_score": data.get("combined_score", 0),
                    }
                )

        return self._create_result(
            success=True,
            data={"is_duplicate": False}
        )
