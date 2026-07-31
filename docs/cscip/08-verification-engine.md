# CyberShield Career Intelligence Platform (CSCIP) - Verification Engine

## Overview

The Verification Engine ensures all job listings are legitimate, accessible, and current before they reach users. It performs real-time validation of job URLs, deadlines, company information, and application status.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      VERIFICATION ENGINE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: Raw Job Data                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    VERIFICATION PIPELINE                             │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 1: Link Verification                                   │   │   │
│  │  │  • HTTP HEAD request to job URL                              │   │   │
│  │  │  • Check response status code (200, 301, 404, 500)          │   │   │
│  │  │  • Detect redirect loops                                     │   │   │
│  │  │  • SSL certificate validation                                │   │   │
│  │  │  • Response time measurement                                 │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 2: Deadline Validation                                 │   │   │
│  │  │  • Parse deadline from job data                              │   │   │
│  │  │  • Check if deadline has passed                              │   │   │
│  │  │  • Calculate days until deadline                             │   │   │
│  │  │  • Flag jobs closing soon (24h, 48h, 7d)                    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 3: Company Verification                                │   │   │
│  │  │  • Validate company name exists                              │   │   │
│  │  │  • Check company website is accessible                       │   │   │
│  │  │  • Verify career page exists                                 │   │   │
│  │  │  • Cross-reference with known company database               │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 4: Application Link Verification                      │   │   │
│  │  │  • Verify apply URL is accessible                            │   │   │
│  │  │  • Check application form is open                            │   │   │
│  │  │  • Detect if position is still available                     │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 5: Duplicate Detection                                 │   │   │
│  │  │  • Check if job already exists in database                   │   │   │
│  │  │  • Compare with recent submissions                           │   │   │
│  │  │  • Flag potential reposts                                    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  Output: VerificationResult                                                 │
│  {                                                                          │
│    "is_valid": true/false,                                                 │
│    "confidence": 0.0-1.0,                                                  │
│    "issues": [...],                                                        │
│    "link_status": "alive" | "broken" | "redirect",                        │
│    "deadline_status": "active" | "closing_soon" | "expired",              │
│    "company_verified": true/false,                                         │
│    "duplicate_detected": true/false                                        │
│  }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Verification Checks

### 1. Link Verification

| Check | Method | Timeout | Retry |
|-------|--------|---------|-------|
| URL Accessibility | HTTP HEAD | 10s | 3x |
| Status Code | Check 200-299 | - | - |
| Redirect Detection | Follow redirects | 10s | - |
| SSL Certificate | Validate cert | 5s | - |
| Response Time | Measure latency | - | - |

**Status Codes:**
```python
class LinkStatus:
    ALIVE = "alive"           # 200-299
    REDIRECT = "redirect"     # 301, 302, 307, 308
    NOT_FOUND = "not_found"   # 404
    FORBIDDEN = "forbidden"   # 403
    SERVER_ERROR = "server_error"  # 500+
    TIMEOUT = "timeout"       # No response
    SSL_ERROR = "ssl_error"   # Certificate issue
```

### 2. Deadline Validation

| Status | Condition | Action |
|--------|-----------|--------|
| `active` | Deadline > 7 days | Normal |
| `closing_soon` | Deadline 1-7 days | Flag for urgency |
| `urgent` | Deadline < 24 hours | High priority alert |
| `expired` | Deadline < now | Mark as inactive |

### 3. Company Verification

| Check | Source | Confidence |
|-------|--------|------------|
| Company exists | Internal database | High |
| Website accessible | HTTP HEAD | Medium |
| Career page exists | HTTP HEAD | Medium |
| Known company list | Static list | High |

### 4. Application Link Verification

| Check | Method |
|-------|--------|
| Apply URL accessible | HTTP HEAD |
| Form is open | Check page content |
| Position available | Check for "closed" indicators |

### 5. Duplicate Detection

| Method | Description |
|--------|-------------|
| URL exact match | Same URL already exists |
| Title + Company | Similar title at same company |
| Semantic similarity | AI-based similarity check |

---

## Implementation Code

```python
# src/cybershield/engines/verification.py

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.domain.models import Job
from cybershield.repositories.job_repository import JobRepository
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)


class VerificationResult:
    """Result of job verification."""
    
    def __init__(self):
        self.is_valid = True
        self.confidence = 1.0
        self.issues: List[str] = []
        self.link_status = "unknown"
        self.deadline_status = "unknown"
        self.company_verified = False
        self.duplicate_detected = False
        self.redirect_url: Optional[str] = None
        self.response_time_ms: Optional[int] = None
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "issues": self.issues,
            "link_status": self.link_status,
            "deadline_status": self.deadline_status,
            "company_verified": self.company_verified,
            "duplicate_detected": self.duplicate_detected,
            "redirect_url": self.redirect_url,
            "response_time_ms": self.response_time_ms,
        }


class VerificationEngine:
    """Engine for verifying job postings."""
    
    # Known legitimate companies
    KNOWN_COMPANIES = {
        "microsoft", "google", "amazon", "cisco", "ibm", "oracle",
        "crowdstrike", "palo alto networks", "fortinet", "checkpoint",
        "rapid7", "qualys", "tenable", "cloudflare", "zscaler",
        "datadog", "elastic", "splunk", "openai", "anthropic",
        "apple", "meta", "netflix", "tesla", "nvidia",
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
    
    async def verify_job(self, job_data: dict) -> Tuple[bool, List[str]]:
        """Verify a job posting and return (is_valid, issues)."""
        result = VerificationResult()
        
        # Run all verification stages
        await self._verify_link(job_data, result)
        await self._verify_deadline(job_data, result)
        await self._verify_company(job_data, result)
        await self._verify_application_link(job_data, result)
        await self._check_duplicates(job_data, result)
        
        # Calculate final validity
        if len(result.issues) > 0:
            result.confidence = max(0.0, 1.0 - (len(result.issues) * 0.2))
        
        # Critical issues make job invalid
        critical_issues = [
            "link_not_found",
            "link_server_error",
            "deadline_expired",
            "duplicate_detected",
        ]
        
        for issue in result.issues:
            if any(critical in issue for critical in critical_issues):
                result.is_valid = False
                break
        
        return result.is_valid, result.issues
    
    async def verify_jobs(self, jobs: List[dict]) -> Tuple[List[dict], List[dict]]:
        """Verify multiple jobs and return (valid_jobs, invalid_jobs)."""
        valid_jobs = []
        invalid_jobs = []
        
        for job in jobs:
            is_valid, issues = await self.verify_job(job)
            if is_valid:
                valid_jobs.append(job)
            else:
                invalid_jobs.append({**job, "_verification_issues": issues})
        
        return valid_jobs, invalid_jobs
    
    async def _verify_link(self, job_data: dict, result: VerificationResult):
        """Verify job URL is accessible."""
        url = job_data.get("url")
        if not url:
            result.issues.append("missing_url")
            return
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(url, follow_redirects=True)
                
                result.response_time_ms = int(response.elapsed.total_seconds() * 1000)
                
                if response.status_code < 400:
                    result.link_status = "alive"
                elif response.status_code == 404:
                    result.link_status = "not_found"
                    result.issues.append("link_not_found")
                elif response.status_code == 403:
                    result.link_status = "forbidden"
                    result.issues.append("link_forbidden")
                elif response.status_code >= 500:
                    result.link_status = "server_error"
                    result.issues.append("link_server_error")
                
                # Check for redirects
                if str(response.url) != url:
                    result.redirect_url = str(response.url)
                    result.link_status = "redirect"
        
        except httpx.TimeoutException:
            result.link_status = "timeout"
            result.issues.append("link_timeout")
        except Exception as e:
            result.link_status = "error"
            result.issues.append(f"link_error: {str(e)}")
    
    async def _verify_deadline(self, job_data: dict, result: VerificationResult):
        """Verify job deadline."""
        deadline = job_data.get("deadline")
        
        if not deadline:
            result.deadline_status = "no_deadline"
            return
        
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except ValueError:
                result.issues.append("invalid_deadline_format")
                return
        
        now = datetime.now(timezone.utc)
        
        if deadline < now:
            result.deadline_status = "expired"
            result.issues.append("deadline_expired")
        elif deadline < now + timedelta(hours=24):
            result.deadline_status = "urgent"
        elif deadline < now + timedelta(days=7):
            result.deadline_status = "closing_soon"
        else:
            result.deadline_status = "active"
    
    async def _verify_company(self, job_data: dict, result: VerificationResult):
        """Verify company information."""
        company = job_data.get("company", "").lower().strip()
        
        if not company:
            result.issues.append("missing_company")
            return
        
        # Check against known companies
        if company in self.KNOWN_COMPANIES:
            result.company_verified = True
            return
        
        # Check company website if provided
        website = job_data.get("company_website")
        if website:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.head(website, follow_redirects=True)
                    if response.status_code < 400:
                        result.company_verified = True
            except Exception:
                pass
        
        # Check if company exists in our database
        existing_company = await self.job_repo.get_company_by_name(company)
        if existing_company:
            result.company_verified = True
    
    async def _verify_application_link(self, job_data: dict, result: VerificationResult):
        """Verify application link is accessible."""
        apply_url = job_data.get("apply_url")
        
        if not apply_url:
            # No separate apply URL, skip
            return
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(apply_url, follow_redirects=True)
                
                if response.status_code == 404:
                    result.issues.append("apply_link_not_found")
                elif response.status_code >= 500:
                    result.issues.append("apply_link_server_error")
        
        except Exception as e:
            result.issues.append(f"apply_link_error: {str(e)}")
    
    async def _check_duplicates(self, job_data: dict, result: VerificationResult):
        """Check for duplicate jobs."""
        url = job_data.get("url")
        
        if url:
            existing = await self.job_repo.get_by_url(url)
            if existing:
                result.duplicate_detected = True
                result.issues.append("duplicate_detected")
                return
        
        # Check by title + company
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        
        if title and company:
            existing = await self.job_repo.find_duplicate(title, company)
            if existing:
                result.duplicate_detected = True
                result.issues.append("potential_duplicate")
    
    async def check_link_health(self, url: str) -> dict:
        """Check if a URL is still accessible."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(url, follow_redirects=True)
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "is_alive": response.status_code < 400,
                    "redirect_url": str(response.url) if str(response.url) != url else None,
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                }
        except Exception as e:
            return {
                "url": url,
                "status_code": None,
                "is_alive": False,
                "error": str(e),
            }
    
    async def verify_all_links(self, job_ids: Optional[List[str]] = None) -> List[dict]:
        """Verify links for multiple jobs."""
        if job_ids:
            jobs = [await self.job_repo.get_by_id(jid) for jid in job_ids]
            jobs = [j for j in jobs if j]
        else:
            jobs = await self.job_repo.get_all(limit=100)
        
        results = []
        for job in jobs:
            result = await self.check_link_health(job.url)
            result["job_id"] = job.id
            result["job_title"] = job.title
            results.append(result)
        
        return results
```

---

## Verification Rules

### Rule Priority

| Priority | Rule | Action |
|----------|------|--------|
| 1 (Critical) | URL returns 404 | Mark job as inactive |
| 2 (Critical) | Deadline expired | Mark job as inactive |
| 3 (Critical) | Duplicate detected | Skip job |
| 4 (High) | URL returns 500 | Flag for manual review |
| 5 (High) | Company not verified | Lower confidence |
| 6 (Medium) | URL redirects | Update URL |
| 7 (Low) | Slow response | Log warning |

### Confidence Scoring

```python
def calculate_confidence(issues: List[str]) -> float:
    """Calculate verification confidence score."""
    base_confidence = 1.0
    
    issue_weights = {
        "missing_url": 0.5,
        "link_not_found": 0.4,
        "link_forbidden": 0.3,
        "link_server_error": 0.3,
        "link_timeout": 0.2,
        "deadline_expired": 0.4,
        "invalid_deadline_format": 0.1,
        "missing_company": 0.2,
        "apply_link_not_found": 0.2,
        "duplicate_detected": 0.5,
        "potential_duplicate": 0.3,
    }
    
    for issue in issues:
        weight = issue_weights.get(issue, 0.1)
        base_confidence -= weight
    
    return max(0.0, base_confidence)
```

---

## Batch Verification

```python
async def batch_verify(
    self,
    job_ids: List[str],
    max_concurrent: int = 10,
) -> Dict[str, VerificationResult]:
    """Verify multiple jobs concurrently."""
    import asyncio
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def verify_with_semaphore(job_id: str):
        async with semaphore:
            job = await self.job_repo.get_by_id(job_id)
            if job:
                is_valid, issues = await self.verify_job(job.to_dict())
                return job_id, VerificationResult(is_valid, issues)
            return job_id, None
    
    tasks = [verify_with_semaphore(jid) for jid in job_ids]
    results = await asyncio.gather(*tasks)
    
    return {job_id: result for job_id, result in results if result}
```

---

## Monitoring & Metrics

| Metric | Description |
|--------|-------------|
| `verification_total` | Total jobs verified |
| `verification_valid` | Jobs passed verification |
| `verification_invalid` | Jobs failed verification |
| `verification_duration_seconds` | Average verification time |
| `link_check_success_rate` | Link check success rate |
| `duplicate_detection_rate` | Duplicate detection rate |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 9: Deduplication Engine](./09-deduplication-engine.md)
