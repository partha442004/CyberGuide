"""
Verification Engine

Verifies job listings by checking:
- Link validity (HTTP status)
- Deadline status
- Company verification
- Application link functionality
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from cybershield.engines.base import BaseEngine, EngineResult

logger = logging.getLogger(__name__)


class VerificationEngine(BaseEngine):
    """
    Verification engine for job listings.

    Checks:
    1. Job URL validity (not 404, not redirect loop)
    2. Deadline status (expired or active)
    3. Company existence
    4. Application link functionality
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("verification", config)
        self.timeout = config.get("timeout", 10) if config else 10
        self.max_retries = config.get("max_retries", 2) if config else 2

    async def _check_url(self, url: str) -> Dict[str, Any]:
        """Check if a URL is accessible."""
        if not url:
            return {"valid": False, "error": "No URL provided"}

        result = {
            "url": url,
            "valid": False,
            "status_code": None,
            "error": None,
            "redirect_url": None,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                # Try HEAD first, fallback to GET if 405
                response = await client.head(url)
                if response.status_code == 405:
                    response = await client.get(url)
                result["status_code"] = response.status_code
                result["valid"] = response.status_code < 400
                result["redirect_url"] = str(response.url) if str(response.url) != url else None

                if response.status_code >= 400:
                    result["error"] = f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            result["error"] = "Timeout"
        except httpx.RequestError as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"

        return result

    def _check_deadline(self, deadline: Optional[datetime]) -> Dict[str, Any]:
        """Check if a job deadline is still active."""
        if not deadline:
            return {"active": True, "expired": False, "days_left": None}

        now = datetime.now(timezone.utc)

        # Ensure deadline has timezone info
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        if deadline < now:
            return {
                "active": False,
                "expired": True,
                "days_left": 0,
                "expired_days_ago": (now - deadline).days,
            }

        days_left = (deadline - now).days
        return {
            "active": True,
            "expired": False,
            "days_left": days_left,
            "urgent": days_left <= 3,
        }

    def _calculate_verification_score(self, checks: List[Dict[str, Any]]) -> float:
        """Calculate overall verification score (0-1)."""
        if not checks:
            return 0.0

        weights = {
            "url_valid": 0.3,
            "apply_url_valid": 0.2,
            "deadline_active": 0.2,
            "company_verified": 0.15,
            "no_redirect_loops": 0.15,
        }

        score = 0.0
        total_weight = 0.0

        for check in checks:
            check_type = check.get("type")
            passed = check.get("passed", False)
            weight = weights.get(str(check_type), 0.1)

            if passed:
                score += weight
            total_weight += weight

        return round(score / total_weight if total_weight > 0 else 0.0, 2)

    async def process(  # type: ignore[override]
        self,
        job: Dict[str, Any],
        **kwargs,
    ) -> EngineResult:
        """
        Verify a job listing.

        Args:
            job: Job dictionary to verify

        Returns:
            EngineResult with verification details
        """
        checks = []

        # Check main job URL
        job_url = job.get("url", "")
        url_check = await self._check_url(job_url)
        checks.append(
            {
                "type": "url_valid",
                "passed": url_check["valid"],
                "details": url_check,
            }
        )

        # Check application URL if different from job URL
        apply_url = job.get("apply_url", "")
        if apply_url and apply_url != job_url:
            apply_check = await self._check_url(apply_url)
            checks.append(
                {
                    "type": "apply_url_valid",
                    "passed": apply_check["valid"],
                    "details": apply_check,
                }
            )
        else:
            checks.append(
                {
                    "type": "apply_url_valid",
                    "passed": True,  # No separate apply URL to check
                    "details": {"note": "No separate application URL"},
                }
            )

        # Check deadline
        deadline = job.get("deadline")
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                deadline = None

        deadline_check = self._check_deadline(deadline)
        checks.append(
            {
                "type": "deadline_active",
                "passed": deadline_check.get("active", True),
                "details": deadline_check,
            }
        )

        # Company verification (basic check)
        company = job.get("company_name", "")
        company_verified = bool(company and len(company) > 1)
        checks.append(
            {
                "type": "company_verified",
                "passed": company_verified,
                "details": {"company": company, "verified": company_verified},
            }
        )

        # Check for redirect loops
        has_redirect_loop = (
            url_check.get("redirect_url") and url_check.get("redirect_url") != job_url
        )
        checks.append(
            {
                "type": "no_redirect_loops",
                "passed": not has_redirect_loop,
                "details": {"redirect_url": url_check.get("redirect_url")},
            }
        )

        # Calculate verification score
        score = self._calculate_verification_score(checks)

        # Determine verification status
        passed_checks = sum(1 for c in checks if c["passed"])
        total_checks = len(checks)
        is_verified = score >= 0.6

        return self._create_result(
            success=True,
            data={
                "is_verified": is_verified,
                "verification_score": score,
                "checks": checks,
                "passed_checks": passed_checks,
                "total_checks": total_checks,
                "status": "verified" if is_verified else "needs_review",
            },
            job_id=job.get("id"),
        )

    async def verify_batch(
        self,
        jobs: List[Dict[str, Any]],
        max_concurrent: int = 5,
    ) -> EngineResult:
        """Verify multiple jobs concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def verify_with_semaphore(job: Dict[str, Any]):
            async with semaphore:
                result = await self.process(job)
                return {"job_id": job.get("id"), "result": result.data}

        tasks = [verify_with_semaphore(job) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verified = [r for r in results if isinstance(r, dict) and r["result"].get("is_verified")]
        failed = [r for r in results if isinstance(r, dict) and not r["result"].get("is_verified")]
        errors = [str(r) for r in results if isinstance(r, Exception)]

        return self._create_result(
            success=True,
            data={
                "verified_count": len(verified),
                "failed_count": len(failed),
                "error_count": len(errors),
                "verified": [r["job_id"] for r in verified],
                "failed": [r["job_id"] for r in failed],
                "errors": errors,
            },
        )
