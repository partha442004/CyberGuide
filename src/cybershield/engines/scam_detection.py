"""
Scam Detection Engine

Detects potential job scams using:
- Pattern matching for known scam indicators
- Content analysis for red flags
- Domain reputation checking
- Confidence scoring
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from cybershield.engines.base import BaseEngine, EngineResult

logger = logging.getLogger(__name__)


class ScamDetectionEngine(BaseEngine):
    """
    Scam detection engine for job listings.

    Identifies potential scams based on:
    1. Red flag keywords and patterns
    2. Suspicious domain patterns
    3. Content analysis
    4. Structural anomalies
    """

    # High-risk scam indicators (score: 80-100)
    CRITICAL_INDICATORS = [
        "training fee", "registration fee", "security deposit",
        "advance payment", "upfront cost", "guaranteed income",
        "work from home guaranteed", "no experience required high salary",
        "mlm", "multi level marketing", "pyramid scheme",
        "money transfer", "wire transfer", "western union",
        "bank account details upfront", "credit card number",
    ]

    # Medium-risk indicators (score: 50-79)
    HIGH_RISK_INDICATORS = [
        "whatsapp number", "telegram only", "no official website",
        "generic email", "gmail", "yahoo", "hotmail",
        "unlimited earning", "earn lakhs", "earn millions",
        "daily payment", "instant joining", "no interview",
        "pay to apply", "refundable fee",
    ]

    # Low-risk indicators (score: 30-49)
    MEDIUM_RISK_INDICATORS = [
        "urgent hiring", "immediate join", "last date today",
        "too good to be true", "no requirements",
        "vague job description", "no company name",
        "personal email contact", "no office address",
    ]

    # Suspicious domain patterns
    SUSPICIOUS_DOMAINS = [
        "blogspot.com", "wordpress.com", "wix.com", "weebly.com",
        "tinyurl.com", "bit.ly",
    ]

    # Known disposable email domains
    DISPOSABLE_EMAIL_DOMAINS = [
        "tempmail.com", "throwaway.email", "guerrillamail.com",
        "mailinator.com", "yopmail.com", "temp-mail.org",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("scam_detection", config)
        self.scam_threshold = config.get("scam_threshold", 50) if config else 50

    def _check_critical_indicators(self, text: str) -> List[Tuple[str, int]]:
        """Check for critical scam indicators."""
        found = []
        text_lower = text.lower()
        for indicator in self.CRITICAL_INDICATORS:
            if indicator.lower() in text_lower:
                found.append((indicator, 90))
        return found

    def _check_high_risk_indicators(self, text: str) -> List[Tuple[str, int]]:
        """Check for high-risk indicators."""
        found = []
        text_lower = text.lower()
        for indicator in self.HIGH_RISK_INDICATORS:
            if indicator.lower() in text_lower:
                found.append((indicator, 65))
        return found

    def _check_medium_risk_indicators(self, text: str) -> List[Tuple[str, int]]:
        """Check for medium-risk indicators."""
        found = []
        text_lower = text.lower()
        for indicator in self.MEDIUM_RISK_INDICATORS:
            if indicator.lower() in text_lower:
                found.append((indicator, 40))
        return found

    def _analyze_domain(self, url: str) -> Dict[str, Any]:
        """Analyze domain for suspicious patterns."""
        if not url:
            return {"suspicious": True, "reason": "No URL provided"}

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check for suspicious domains
            for suspicious in self.SUSPICIOUS_DOMAINS:
                if suspicious in domain:
                    return {"suspicious": True, "reason": f"Hosted on {suspicious}"}

            # Check for typosquatting (simple check)
            known_companies = ["microsoft", "google", "amazon", "cisco", "ibm"]
            for company in known_companies:
                if company in domain and company + ".com" != domain:
                    return {"suspicious": True, "reason": f"Possible typosquatting of {company}"}

            # Check for unusual TLDs
            suspicious_tlds = [".xyz", ".top", ".club", ".site", ".online"]
            if any(domain.endswith(tld) for tld in suspicious_tlds):
                return {"suspicious": True, "reason": "Unusual TLD"}

            return {"suspicious": False}

        except Exception:
            return {"suspicious": True, "reason": "Invalid URL format"}

    def _analyze_email(self, email: str) -> Dict[str, Any]:
        """Analyze email for suspicious patterns."""
        if not email:
            return {"suspicious": False}

        email_lower = email.lower()

        # Check for disposable email
        for disposable in self.DISPOSABLE_EMAIL_DOMAINS:
            if disposable in email_lower:
                return {"suspicious": True, "reason": "Disposable email address"}

        # Check for personal email in professional context
        personal_providers = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        for provider in personal_providers:
            if provider in email_lower:
                return {"suspicious": True, "reason": f"Personal email ({provider})"}

        return {"suspicious": False}

    def _analyze_content(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze job content for scam patterns."""
        title = job.get("title", "")
        description = job.get("description", "")
        company = job.get("company_name", "")

        combined_text = f"{title} {description} {company}"

        # Gather all indicators
        critical = self._check_critical_indicators(combined_text)
        high_risk = self._check_high_risk_indicators(combined_text)
        medium_risk = self._check_medium_risk_indicators(combined_text)

        all_indicators = critical + high_risk + medium_risk

        # Calculate content score
        if not all_indicators:
            score = 0
        else:
            max_score = max(score for _, score in all_indicators)
            # If any critical indicator found, use max score directly
            if critical:
                score = max_score
            else:
                avg_score = sum(score for _, score in all_indicators) / len(all_indicators)
                score = (max_score * 0.6) + (avg_score * 0.4)

        return {
            "score": min(score, 100),
            "critical_indicators": [i[0] for i in critical],
            "high_risk_indicators": [i[0] for i in high_risk],
            "medium_risk_indicators": [i[0] for i in medium_risk],
            "total_indicators": len(all_indicators),
        }

    def _calculate_scam_score(
        self,
        content_analysis: Dict[str, Any],
        domain_analysis: Dict[str, Any],
        email_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate final scam confidence score."""
        # Weighted scoring

        base_score = content_analysis.get("score", 0)

        # Domain adjustment
        domain_penalty = 25 if domain_analysis.get("suspicious") else 0

        # Email adjustment
        email_penalty = 15 if email_analysis.get("suspicious") else 0

        final_score = min(100, base_score + domain_penalty + email_penalty)

        # Determine risk level
        if final_score >= 70:
            risk_level = "critical"
            action = "block"
        elif final_score >= 50:
            risk_level = "high"
            action = "warn"
        elif final_score >= 30:
            risk_level = "medium"
            action = "flag"
        else:
            risk_level = "low"
            action = "allow"

        return {
            "score": round(final_score, 1),
            "risk_level": risk_level,
            "action": action,
            "breakdown": {
                "content_score": content_analysis.get("score", 0),
                "domain_penalty": domain_penalty,
                "email_penalty": email_penalty,
            },
        }

    async def process(
        self,
        job: Dict[str, Any],
        **kwargs,
    ) -> EngineResult:
        """
        Analyze a job for scam indicators.

        Args:
            job: Job dictionary to analyze

        Returns:
            EngineResult with scam analysis
        """
        # Content analysis
        content_analysis = self._analyze_content(job)

        # Domain analysis
        domain_analysis = self._analyze_domain(job.get("url", ""))

        # Email analysis (if available)
        email = job.get("hr_email") or job.get("contact_email", "")
        email_analysis = self._analyze_email(email)

        # Calculate final score
        scam_result = self._calculate_scam_score(
            content_analysis, domain_analysis, email_analysis
        )

        # Build flags list
        flags = []
        if content_analysis.get("critical_indicators"):
            flags.extend([f"CRITICAL: {i}" for i in content_analysis["critical_indicators"]])
        if content_analysis.get("high_risk_indicators"):
            flags.extend([f"HIGH: {i}" for i in content_analysis["high_risk_indicators"]])
        if domain_analysis.get("suspicious"):
            flags.append(f"DOMAIN: {domain_analysis.get('reason')}")
        if email_analysis.get("suspicious"):
            flags.append(f"EMAIL: {email_analysis.get('reason')}")

        return self._create_result(
            success=True,
            data={
                "scam_score": scam_result["score"],
                "risk_level": scam_result["risk_level"],
                "action": scam_result["action"],
                "is_scam": scam_result["score"] >= self.scam_threshold,
                "flags": flags,
                "content_analysis": content_analysis,
                "domain_analysis": domain_analysis,
                "email_analysis": email_analysis,
                "breakdown": scam_result["breakdown"],
            },
            job_id=job.get("id"),
        )

    async def analyze_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> EngineResult:
        """Analyze multiple jobs for scams."""
        results = []
        scam_count = 0

        for job in jobs:
            result = await self.process(job)
            if result.success:
                is_scam = result.data.get("is_scam", False)
                if is_scam:
                    scam_count += 1
                results.append({
                    "job_id": job.get("id"),
                    "scam_score": result.data.get("scam_score"),
                    "risk_level": result.data.get("risk_level"),
                    "is_scam": is_scam,
                })

        return self._create_result(
            success=True,
            data={
                "total_analyzed": len(jobs),
                "scam_detected": scam_count,
                "safe_jobs": len(jobs) - scam_count,
                "results": results,
            }
        )
