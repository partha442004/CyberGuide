# CyberShield Career Intelligence Platform (CSCIP) - Deduplication Engine

## Overview

The Deduplication Engine eliminates duplicate job listings across multiple sources using hash-based matching, semantic similarity, and embedding-based comparison. It ensures users never see the same job twice.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEDUPLICATION ENGINE ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: Raw Jobs from multiple sources                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DEDUPLICATION PIPELINE                            │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 1: URL Normalization                                    │   │   │
│  │  │  • Remove tracking parameters (utm_*, ref, etc.)             │   │   │
│  │  │  • Normalize URL format (lowercase, remove trailing /)       │   │   │
│  │  │  • Handle redirects                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 2: Hash-based Matching                                 │   │   │
│  │  │  • MD5 hash of normalized URL                                │   │   │
│  │  │  • SHA256 hash of title + company                            │   │   │
│  │  │  • Exact match against database                              │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 3: Fuzzy Matching                                      │   │   │
│  │  │  • Title similarity (SequenceMatcher)                        │   │   │
│  │  │  • Company name normalization                                │   │   │
│  │  │  • Location normalization                                    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 4: Semantic Similarity (AI)                            │   │   │
│  │  │  • Embedding-based comparison                                │   │   │
│  │  │  • Cosine similarity score                                   │   │   │
│  │  │  • Threshold-based decision                                  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 5: Duplicate Grouping                                  │   │   │
│  │  │  • Group duplicates together                                 │   │   │
│  │  │  • Select canonical (best) version                           │   │   │
│  │  │  • Mark duplicates                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  Output: Unique Jobs (deduplicated)                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deduplication Strategies

### 1. URL-based Deduplication

| Strategy | Method | Confidence |
|----------|--------|------------|
| Exact URL match | Direct comparison | 100% |
| Normalized URL | Remove params, normalize | 95% |
| Canonical URL | Follow redirects | 90% |

**URL Normalization Rules:**
```python
def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    parsed = urlparse(url.lower())
    
    # Remove tracking parameters
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'ref', 'source', 'fbclid', 'gclid', 'mc_cid', 'mc_eid',
    }
    
    query_params = parse_qs(parsed.query)
    cleaned_params = {
        k: v for k, v in query_params.items()
        if k.lower() not in tracking_params
    }
    
    # Reconstruct URL
    cleaned_query = urlencode(cleaned_params, doseq=True)
    normalized = parsed._replace(query=cleaned_query, fragment='')
    
    # Remove trailing slash
    path = normalized.path.rstrip('/') or '/'
    
    return urlunparse(normalized._replace(path=path))
```

### 2. Hash-based Deduplication

| Hash Type | Input | Use Case |
|-----------|-------|----------|
| URL Hash | Normalized URL | Exact URL match |
| Title+Company Hash | title + company | Same job, different URL |
| Content Hash | Description snippet | Similar content |

**Hash Implementation:**
```python
import hashlib

def compute_job_hash(job_data: dict) -> str:
    """Compute hash for job deduplication."""
    # Primary hash: URL
    url = normalize_url(job_data.get("url", ""))
    url_hash = hashlib.md5(url.encode()).hexdigest()
    
    # Secondary hash: Title + Company
    title = job_data.get("title", "").lower().strip()
    company = normalize_company(job_data.get("company", ""))
    title_company = f"{title}|{company}"
    tc_hash = hashlib.sha256(title_company.encode()).hexdigest()
    
    return f"{url_hash}:{tc_hash}"
```

### 3. Fuzzy Matching

| Algorithm | Threshold | Speed | Accuracy |
|-----------|-----------|-------|----------|
| SequenceMatcher | 0.85 | Fast | Medium |
| Levenshtein | 0.80 | Medium | High |
| Jaro-Winkler | 0.85 | Fast | High |

**Fuzzy Match Implementation:**
```python
from difflib import SequenceMatcher

def calculate_similarity(job1: dict, job2: dict) -> float:
    """Calculate similarity score between two jobs."""
    scores = []
    
    # Title similarity
    title1 = job1.get("title", "").lower()
    title2 = job2.get("title", "").lower()
    scores.append(SequenceMatcher(None, title1, title2).ratio())
    
    # Company similarity
    company1 = normalize_company(job1.get("company", ""))
    company2 = normalize_company(job2.get("company", ""))
    scores.append(SequenceMatcher(None, company1, company2).ratio())
    
    # Location similarity
    loc1 = normalize_location(job1.get("location", ""))
    loc2 = normalize_location(job2.get("location", ""))
    scores.append(SequenceMatcher(None, loc1, loc2).ratio())
    
    # Weighted average
    weights = [0.5, 0.3, 0.2]
    return sum(s * w for s, w in zip(scores, weights))
```

### 4. Semantic Similarity (AI-powered)

| Method | Model | Accuracy | Speed |
|--------|-------|----------|-------|
| TF-IDF | scikit-learn | Medium | Fast |
| sentence-transformers | all-MiniLM-L6-v2 | High | Medium |
| Ollama embeddings | nomic-embed-text | High | Slow |

**Semantic Similarity Implementation:**
```python
from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticDeduplicator:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.threshold = 0.85
    
    def compute_embedding(self, text: str) -> np.ndarray:
        """Compute embedding for text."""
        return self.model.encode(text)
    
    def calculate_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings."""
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
    
    def is_duplicate(self, job1: dict, job2: dict) -> bool:
        """Check if two jobs are duplicates."""
        text1 = f"{job1.get('title', '')} {job1.get('description', '')[:500]}"
        text2 = f"{job2.get('title', '')} {job2.get('description', '')[:500]}"
        
        emb1 = self.compute_embedding(text1)
        emb2 = self.compute_embedding(text2)
        
        similarity = self.calculate_similarity(emb1, emb2)
        return similarity >= self.threshold
```

---

## Canonical Job Selection

When duplicates are found, the engine selects the best version as canonical:

### Selection Criteria

| Priority | Criterion | Weight |
|----------|-----------|--------|
| 1 | Official company website | +50 |
| 2 | More complete data | +30 |
| 3 | Earlier posting date | +20 |
| 4 | Higher source reliability | +15 |
| 5 | More recent update | +10 |

**Canonical Selection Algorithm:**
```python
def select_canonical(jobs: List[dict]) -> dict:
    """Select the best version as canonical."""
    scored_jobs = []
    
    for job in jobs:
        score = 0
        
        # Official website bonus
        if is_official_website(job.get("url", "")):
            score += 50
        
        # Data completeness
        fields = ["description", "salary_min", "salary_max", "required_skills", "deadline"]
        completeness = sum(1 for f in fields if job.get(f))
        score += completeness * 6
        
        # Posting date (earlier is better)
        if job.get("posted_at"):
            days_old = (datetime.now() - job["posted_at"]).days
            score += max(0, 20 - days_old)
        
        # Source reliability
        source_scores = {
            "company_career": 40,
            "linkedin": 30,
            "indeed": 25,
            "glassdoor": 25,
            "other": 10,
        }
        score += source_scores.get(job.get("source", ""), 10)
        
        scored_jobs.append((score, job))
    
    # Return job with highest score
    scored_jobs.sort(key=lambda x: x[0], reverse=True)
    return scored_jobs[0][1]
```

---

## Implementation Code

```python
# src/cybershield/engines/deduplication.py

import hashlib
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.domain.models import Job, DuplicateGroup
from cybershield.repositories.job_repository import JobRepository
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)


class DeduplicationEngine:
    """Engine for deduplicating job postings."""
    
    SIMILARITY_THRESHOLD = 0.85
    URL_TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'ref', 'source', 'fbclid', 'gclid', 'mc_cid', 'mc_eid',
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
    
    async def filter_unique(self, jobs: List[dict]) -> List[dict]:
        """Filter out duplicate jobs from a list."""
        unique_jobs = []
        seen_hashes: Set[str] = set()
        
        for job_data in jobs:
            # Compute hash
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
    
    async def find_duplicates_in_database(
        self,
        threshold: float = 0.85,
        limit: int = 1000,
    ) -> List[Tuple[Job, Job, float]]:
        """Find potential duplicates in the database."""
        from sqlalchemy import select
        
        query = select(Job).where(Job.is_active == True).limit(limit)
        result = await self.session.execute(query)
        all_jobs = list(result.scalars().all())
        
        duplicates = []
        seen_pairs: Set[Tuple[str, str]] = set()
        
        for i, job1 in enumerate(all_jobs):
            for job2 in all_jobs[i + 1:]:
                pair_key = tuple(sorted([job1.id, job2.id]))
                if pair_key in seen_pairs:
                    continue
                
                similarity = self._calculate_similarity(
                    self._job_to_dict(job1),
                    self._job_to_dict(job2),
                )
                
                if similarity >= threshold:
                    duplicates.append((job1, job2, similarity))
                    seen_pairs.add(pair_key)
        
        return duplicates
    
    async def merge_duplicates(
        self,
        canonical_id: str,
        duplicate_ids: List[str],
    ) -> Job:
        """Merge duplicates into canonical job."""
        canonical = await self.job_repo.get_by_id(canonical_id)
        if not canonical:
            raise ValueError(f"Canonical job {canonical_id} not found")
        
        for dup_id in duplicate_ids:
            duplicate = await self.job_repo.get_by_id(dup_id)
            if not duplicate:
                continue
            
            # Merge data from duplicate to canonical
            await self._merge_job_data(canonical, duplicate)
            
            # Create duplicate group record
            dup_group = DuplicateGroup(
                canonical_job_id=canonical_id,
                duplicate_job_id=dup_id,
                similarity_score=1.0,
                match_type="manual_merge",
            )
            self.session.add(dup_group)
            
            # Deactivate duplicate
            duplicate.is_active = False
            await self.session.flush()
        
        return canonical
    
    def _compute_hash(self, job_data: dict) -> str:
        """Compute hash for job deduplication."""
        # URL hash
        url = self._normalize_url(job_data.get("url", ""))
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        # Title + Company hash
        title = job_data.get("title", "").lower().strip()
        company = self._normalize_company(job_data.get("company", ""))
        title_company = f"{title}|{company}"
        tc_hash = hashlib.sha256(title_company.encode()).hexdigest()
        
        return f"{url_hash}:{tc_hash}"
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        if not url:
            return ""
        
        try:
            parsed = urlparse(url.lower())
            
            # Remove tracking parameters
            query_params = parse_qs(parsed.query)
            cleaned_params = {
                k: v for k, v in query_params.items()
                if k.lower() not in self.URL_TRACKING_PARAMS
            }
            
            # Reconstruct URL
            cleaned_query = urlencode(cleaned_params, doseq=True)
            normalized = parsed._replace(query=cleaned_query, fragment='')
            
            # Remove trailing slash
            path = normalized.path.rstrip('/') or '/'
            
            return urlunparse(normalized._replace(path=path))
        except Exception:
            return url.lower()
    
    def _normalize_company(self, company: str) -> str:
        """Normalize company name for comparison."""
        if not company:
            return ""
        
        company = company.lower().strip()
        
        # Remove common suffixes
        suffixes = [
            " inc", " inc.", " llc", " ltd", " ltd.", " corp", " corp.",
            " corporation", " company", " co", " co.", " group", " group.",
        ]
        for suffix in suffixes:
            if company.endswith(suffix):
                company = company[:-len(suffix)].strip()
        
        # Remove special characters
        company = re.sub(r'[^\w\s]', '', company)
        
        # Normalize whitespace
        company = ' '.join(company.split())
        
        return company
    
    def _normalize_location(self, location: str) -> str:
        """Normalize location for comparison."""
        if not location:
            return ""
        
        location = location.lower().strip()
        
        # Common location normalizations
        location_map = {
            "san francisco": "sf",
            "new york": "nyc",
            "los angeles": "la",
            "bangalore": "bengaluru",
            "bombay": "mumbai",
        }
        
        for key, value in location_map.items():
            if key in location:
                location = location.replace(key, value)
        
        return location
    
    def _calculate_similarity(self, job1: dict, job2: dict) -> float:
        """Calculate similarity score between two jobs."""
        scores = []
        
        # Title similarity (weight: 0.5)
        title1 = job1.get("title", "").lower()
        title2 = job2.get("title", "").lower()
        scores.append(SequenceMatcher(None, title1, title2).ratio())
        
        # Company similarity (weight: 0.3)
        company1 = self._normalize_company(job1.get("company", ""))
        company2 = self._normalize_company(job2.get("company", ""))
        scores.append(SequenceMatcher(None, company1, company2).ratio())
        
        # Location similarity (weight: 0.2)
        loc1 = self._normalize_location(job1.get("location", ""))
        loc2 = self._normalize_location(job2.get("location", ""))
        scores.append(SequenceMatcher(None, loc1, loc2).ratio())
        
        # Weighted average
        weights = [0.5, 0.3, 0.2]
        return sum(s * w for s, w in zip(scores, weights))
    
    async def _find_existing(self, job_data: dict) -> Optional[Job]:
        """Find existing job that matches the given data."""
        # Check by URL
        url = job_data.get("url")
        if url:
            existing = await self.job_repo.get_by_url(url)
            if existing:
                return existing
        
        # Check by title + company
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        source = job_data.get("source", "unknown")
        
        if title and company:
            existing = await self.job_repo.find_duplicate(title, company, source)
            if existing:
                return existing
        
        return None
    
    def _job_to_dict(self, job: Job) -> dict:
        """Convert Job model to dict for comparison."""
        return {
            "title": job.title,
            "company": job.company,
            "url": job.url,
            "location": job.location,
            "description": job.description,
        }
    
    async def _merge_job_data(self, canonical: Job, duplicate: Job):
        """Merge data from duplicate into canonical."""
        # Update empty fields with duplicate data
        if not canonical.description and duplicate.description:
            canonical.description = duplicate.description
        
        if not canonical.salary_min and duplicate.salary_min:
            canonical.salary_min = duplicate.salary_min
        
        if not canonical.salary_max and duplicate.salary_max:
            canonical.salary_max = duplicate.salary_max
        
        if not canonical.deadline and duplicate.deadline:
            canonical.deadline = duplicate.deadline
        
        # Merge skills
        if duplicate.required_skills:
            existing_skills = set(canonical.required_skills or [])
            existing_skills.update(duplicate.required_skills)
            canonical.required_skills = list(existing_skills)
        
        # Keep the earlier posting date
        if duplicate.posted_at and (not canonical.posted_at or duplicate.posted_at < canonical.posted_at):
            canonical.posted_at = duplicate.posted_at
        
        await self.session.flush()
```

---

## Performance Optimization

### Batch Processing

```python
async def batch_deduplicate(
    self,
    jobs: List[dict],
    batch_size: int = 100,
) -> List[dict]:
    """Deduplicate jobs in batches."""
    unique_jobs = []
    
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i + batch_size]
        unique_batch = await self.filter_unique(batch)
        unique_jobs.extend(unique_batch)
    
    return unique_jobs
```

### Caching

```python
from cybershield.utils.cache import cached

@cached(ttl=3600, prefix="dedup")
async def get_existing_urls(self) -> Set[str]:
    """Get all existing job URLs (cached for 1 hour)."""
    urls = await self.job_repo.get_all_urls()
    return set(urls)
```

---

## Metrics & Monitoring

| Metric | Description |
|--------|-------------|
| `dedup_total_processed` | Total jobs processed |
| `dedup_unique_found` | Unique jobs found |
| `dedup_duplicates_removed` | Duplicates removed |
| `dedup_hash_matches` | Hash-based matches |
| `dedup_fuzzy_matches` | Fuzzy matches |
| `dedup_semantic_matches` | Semantic matches |
| `dedup_processing_time_seconds` | Processing time |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 10: Scam Detection Engine](./10-scam-detection-engine.md)
