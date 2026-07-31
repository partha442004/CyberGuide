# CyberShield Career Intelligence Platform (CSCIP) - Scam Detection Engine

## Overview

The Scam Detection Engine protects users from fraudulent job postings using AI-powered analysis, rule-based detection, and pattern matching. It generates a scam confidence score (0-100) for every job listing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SCAM DETECTION ENGINE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: Raw Job Data                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ANALYSIS PIPELINE                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 1: Rule-Based Detection                                │   │   │
│  │  │  • Pattern matching for known scam indicators                │   │   │
│  │  │  • Keyword analysis (training fee, advance payment)          │   │   │
│  │  │  • URL suspiciousness check                                  │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 2: Domain Analysis                                     │   │   │
│  │  │  • Email domain verification                                 │   │   │
│  │  │  • Website domain age check                                  │   │   │
│  │  │  • Typosquatting detection                                   │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 3: Content Analysis                                    │   │   │
│  │  │  • Description copied detection                              │   │   │
│  │  │  • Unrealistic promises detection                            │   │   │
│  │  │  • Grammar/spelling analysis                                 │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 4: AI Analysis (Ollama/Gemini)                         │   │   │
│  │  │  • LLM-based scam probability assessment                     │   │   │
│  │  │  • Context-aware analysis                                    │   │   │
│  │  │  • Confidence scoring                                        │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                              │                                       │   │
│  │                              ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ Stage 5: Score Aggregation                                   │   │   │
│  │  │  • Combine all signals                                       │   │   │
│  │  │  • Generate final scam score (0-100)                         │   │   │
│  │  │  • Generate explanation                                      │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  Output: ScamResult                                                         │
│  {                                                                          │
│    "scam_score": 75,        // 0-100 (100 = definitely scam)              │
│    "confidence": 0.85,      // 0-1.0                                      │
│    "is_scam": true,         // score > 70                                  │
│    "flags": [...],          // Detected indicators                         │
│    "reasons": [...],        // Human-readable explanations                 │
│    "risk_level": "high"     // low, medium, high, critical                 │
│  }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Scam Indicators

### Critical Red Flags (Weight: 80-100)

| Indicator | Pattern | Weight | Description |
|-----------|---------|--------|-------------|
| Training Fee | "training fee", "pay for training", "registration fee" | 95 | Requests payment for training |
| Advance Payment | "advance payment", "security deposit", "refundable fee" | 95 | Requests upfront payment |
| Guaranteed Income | "guaranteed income", " assured salary", "100% placement" | 90 | Unrealistic promises |
| Fake Domain | Domain doesn't match company | 90 | Impersonation attempt |
| No Company Info | Missing company details | 85 | Lack of transparency |

### High Risk Flags (Weight: 50-79)

| Indicator | Pattern | Weight | Description |
|-----------|---------|--------|-------------|
| Disposable Email | temp-mail, guerrillamail, 10minutemail | 75 | Temporary email domain |
| Typosquatting | Similar to legitimate domain | 80 | Domain impersonation |
| Vague Description | Job description is unclear | 60 | Lack of detail |
| No Application Link | Missing apply URL | 55 | Suspicious omission |
| Unusual Contact | Personal email for business | 65 | Non-professional contact |

### Medium Risk Flags (Weight: 30-49)

| Indicator | Pattern | Weight | Description |
|-----------|---------|--------|-------------|
| Urgency Pressure | "apply now", "limited time", "last chance" | 45 | Creates false urgency |
| Too Good to Be True | Salary way above market | 50 | Unrealistic compensation |
| Generic Description | Copied from other sources | 40 | Lack of originality |
| No Salary Info | Missing compensation details | 35 | Incomplete listing |
| Missing Benefits | No benefits mentioned | 30 | Incomplete information |

### Low Risk Flags (Weight: 10-29)

| Indicator | Pattern | Weight | Description |
|-----------|---------|--------|-------------|
| New Domain | Recently registered domain | 25 | Young website |
| No Social Media | Missing social presence | 20 | Limited online presence |
| Poor Grammar | Spelling/grammar issues | 15 | Quality concerns |
| Incomplete Profile | Missing company size/industry | 15 | Limited information |

---

## Scam Score Calculation

```python
def calculate_scam_score(flags: List[dict]) -> tuple[int, float]:
    """Calculate scam score and confidence."""
    
    if not flags:
        return 0, 0.5
    
    # Weighted sum of flags
    total_weight = sum(f["weight"] for f in flags)
    max_possible = len(flags) * 100
    
    # Normalize to 0-100
    raw_score = (total_weight / max_possible) * 100
    
    # Apply penalty for critical flags
    critical_flags = [f for f in flags if f["weight"] >= 80]
    if critical_flags:
        raw_score = max(raw_score, 70 + len(critical_flags) * 10)
    
    # Cap at 100
    scam_score = min(100, int(raw_score))
    
    # Calculate confidence based on flag consistency
    flag_weights = [f["weight"] for f in flags]
    if len(flag_weights) > 1:
        variance = sum((w - sum(flag_weights)/len(flag_weights))**2 for w in flag_weights) / len(flag_weights)
        confidence = max(0.5, 1.0 - (variance / 10000))
    else:
        confidence = 0.6
    
    return scam_score, round(confidence, 2)
```

---

## Risk Levels

| Score Range | Risk Level | Action |
|-------------|------------|--------|
| 0-30 | **Low** | Normal processing |
| 31-50 | **Medium** | Flag for review |
| 51-70 | **High** | Warn user, reduce visibility |
| 71-100 | **Critical** | Block from listings, alert user |

---

## Implementation Code

```python
# src/cybershield/engines/scam_detection.py

import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.config import get_settings
from cybershield.domain.models import Job, ScamScore
from cybershield.repositories.job_repository import JobRepository
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ScamIndicator:
    """Represents a detected scam indicator."""
    
    def __init__(self, name: str, description: str, weight: int, evidence: str):
        self.name = name
        self.description = description
        self.weight = weight
        self.evidence = evidence
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "evidence": self.evidence,
        }


class ScamDetectionEngine:
    """Engine for detecting scam job postings."""
    
    # Suspicious patterns
    SCAM_PATTERNS = {
        # Critical (weight: 80-100)
        "training_fee": {
            "patterns": [
                r"training\s+fee",
                r"pay\s+for\s+training",
                r"registration\s+fee",
                r"fee\s+for\s+training",
                r"security\s+deposit",
                r"refundable\s+fee",
            ],
            "weight": 95,
            "description": "Requests payment for training or registration",
        },
        "advance_payment": {
            "patterns": [
                r"advance\s+payment",
                r"upfront\s+payment",
                r"pay\s+before",
                r"initial\s+payment",
            ],
            "weight": 95,
            "description": "Requests advance payment before joining",
        },
        "guaranteed_income": {
            "patterns": [
                r"guaranteed\s+income",
                r"assured\s+salary",
                r"100%\s+placement",
                r"guaranteed\s+job",
                r"no\s+risk",
            ],
            "weight": 90,
            "description": "Makes unrealistic guarantees",
        },
        
        # High Risk (weight: 50-79)
        "disposable_email": {
            "patterns": [
                r"@temp-mail\.org",
                r"@guerrillamail\.com",
                r"@10minutemail\.com",
                r"@mailinator\.com",
                r"@yopmail\.com",
                r"@throwaway\.email",
            ],
            "weight": 75,
            "description": "Uses disposable email domain",
        },
        "urgency_pressure": {
            "patterns": [
                r"apply\s+now",
                r"limited\s+time",
                r"last\s+chance",
                r"urgent\s+hiring",
                r"positions\s+filling\s+fast",
                r"only\s+\d+\s+spots",
            ],
            "weight": 45,
            "description": "Creates false urgency to pressure applicants",
        },
        "too_good_to_be_true": {
            "patterns": [
                r"earn\s+\$?\d{4,}.*per\s+week",
                r"make\s+money\s+fast",
                r"easy\s+money",
                r"work\s+from\s+home.*\$\d+",
            ],
            "weight": 50,
            "description": "Salary or benefits seem unrealistic",
        },
    }
    
    # Disposable email domains
    DISPOSABLE_DOMAINS = {
        "temp-mail.org", "guerrillamail.com", "10minutemail.com",
        "mailinator.com", "yopmail.com", "throwaway.email",
        "tempmail.com", "dispostable.com", "maildrop.cc",
    }
    
    # Typosquatting detection
    TYPOSQUAT_PATTERNS = {
        "microsoft": ["micr0soft", "micros0ft", "mircosoft", "microsoft-careers"],
        "google": ["g00gle", "goog1e", "google-careers", "goggle"],
        "amazon": ["amaz0n", "amazone", "amazon-jobs", "amzon"],
        "cisco": ["c1sco", "ciscc0", "cisco-careers"],
        "crowdstrike": ["crowdstrike-secure", "crowdstrlke"],
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
    
    async def analyze_job(self, job_data: dict) -> Dict[str, Any]:
        """Analyze a job for scam indicators."""
        flags: List[ScamIndicator] = []
        
        # Stage 1: Rule-based detection
        await self._check_scam_patterns(job_data, flags)
        
        # Stage 2: Domain analysis
        await self._check_domain(job_data, flags)
        
        # Stage 3: Content analysis
        await self._check_content(job_data, flags)
        
        # Stage 4: AI analysis (optional)
        if settings.is_ai_configured:
            await self._ai_analysis(job_data, flags)
        
        # Stage 5: Calculate final score
        scam_score, confidence = self._calculate_score(flags)
        
        # Generate result
        result = {
            "scam_score": scam_score,
            "confidence": confidence,
            "is_scam": scam_score > 70,
            "risk_level": self._get_risk_level(scam_score),
            "flags": [f.to_dict() for f in flags],
            "reasons": [f.description for f in flags],
        }
        
        # Save to database
        await self._save_result(job_data, result)
        
        return result
    
    async def _check_scam_patterns(self, job_data: dict, flags: List[ScamIndicator]):
        """Check for known scam patterns."""
        text = f"{job_data.get('title', '')} {job_data.get('description', '')}".lower()
        
        for pattern_name, pattern_config in self.SCAM_PATTERNS.items():
            for pattern in pattern_config["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    flags.append(ScamIndicator(
                        name=pattern_name,
                        description=pattern_config["description"],
                        weight=pattern_config["weight"],
                        evidence=pattern,
                    ))
                    break  # One match per pattern type is enough
    
    async def _check_domain(self, job_data: dict, flags: List[ScamIndicator]):
        """Check domain-related scam indicators."""
        url = job_data.get("url", "")
        apply_url = job_data.get("apply_url", "")
        hr_email = job_data.get("hr_email", "")
        company = job_data.get("company", "").lower()
        
        # Check for typosquatting
        for legitimate, typosquats in self.TYPOSQUAT_PATTERNS.items():
            if any(typo in url.lower() for typo in typosquats):
                flags.append(ScamIndicator(
                    name="typosquatting",
                    description=f"Domain resembles {legitimate} but is suspicious",
                    weight=80,
                    evidence=url,
                ))
        
        # Check email domain
        if hr_email:
            email_domain = hr_email.split("@")[-1] if "@" in hr_email else ""
            
            if email_domain in self.DISPOSABLE_DOMAINS:
                flags.append(ScamIndicator(
                    name="disposable_email",
                    description="Uses disposable email domain",
                    weight=75,
                    evidence=hr_email,
                ))
            
            # Check if email domain matches company
            if company and email_domain:
                company_words = company.replace(" ", "")
                if company_words not in email_domain:
                    flags.append(ScamIndicator(
                        name="email_mismatch",
                        description="Email domain doesn't match company name",
                        weight=60,
                        evidence=hr_email,
                    ))
        
        # Check if company website matches
        company_website = job_data.get("company_website", "")
        if company_website and url:
            company_domain = urlparse(company_website).netloc.replace("www.", "")
            job_domain = urlparse(url).netloc.replace("www.", "")
            
            if company_domain and job_domain and company_domain != job_domain:
                if company.lower().replace(" ", "") not in job_domain:
                    flags.append(ScamIndicator(
                        name="domain_mismatch",
                        description="Job URL doesn't match company website",
                        weight=70,
                        evidence=url,
                    ))
    
    async def _check_content(self, job_data: dict, flags: List[ScamIndicator]):
        """Check job content for scam indicators."""
        description = job_data.get("description", "")
        
        # Check for copied/generic description
        if description:
            # Very short description
            if len(description) < 100:
                flags.append(ScamIndicator(
                    name="vague_description",
                    description="Job description is unusually short",
                    weight=50,
                    evidence=f"Description length: {len(description)} chars",
                ))
            
            # Check for generic phrases
            generic_phrases = [
                "we are looking for",
                "dynamic candidate",
                "self-motivated",
                "team player",
                "excellent communication",
            ]
            
            generic_count = sum(1 for phrase in generic_phrases if phrase in description.lower())
            if generic_count >= 3:
                flags.append(ScamIndicator(
                    name="generic_description",
                    description="Job description appears generic/copied",
                    weight=40,
                    evidence=f"Found {generic_count} generic phrases",
                ))
        
        # Check for unrealistic promises
        salary_min = job_data.get("salary_min")
        salary_max = job_data.get("salary_max")
        experience = job_data.get("experience_level", "")
        
        if salary_min and salary_max:
            avg_salary = (salary_min + salary_max) / 2
            
            # Entry level with very high salary
            if experience in ["entry", "junior", "internship"] and avg_salary > 150000:
                flags.append(ScamIndicator(
                    name="unrealistic_salary",
                    description="Salary seems unrealistic for experience level",
                    weight=50,
                    evidence=f"${avg_salary:,.0f} for {experience} level",
                ))
    
    async def _ai_analysis(self, job_data: dict, flags: List[ScamIndicator]):
        """Use AI to analyze job for scam indicators."""
        try:
            prompt = f"""Analyze this job posting for scam indicators. Return JSON with:
- scam_probability: 0-100
- confidence: 0-1
- reasons: list of reasons

Job Title: {job_data.get('title', 'N/A')}
Company: {job_data.get('company', 'N/A')}
Description: {job_data.get('description', 'N/A')[:500]}
URL: {job_data.get('url', 'N/A')}
Salary: {job_data.get('salary_min', 'N/A')} - {job_data.get('salary_max', 'N/A')}"""

            if settings.gemini_api_key:
                result = await self._analyze_with_gemini(prompt)
            elif settings.ollama_base_url:
                result = await self._analyze_with_ollama(prompt)
            else:
                return
            
            if result and result.get("scam_probability", 0) > 50:
                flags.append(ScamIndicator(
                    name="ai_detected_scam",
                    description=f"AI detected potential scam ({result['scam_probability']}% probability)",
                    weight=result["scam_probability"],
                    evidence=str(result.get("reasons", [])),
                ))
        
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
    
    async def _analyze_with_gemini(self, prompt: str) -> Optional[dict]:
        """Analyze using Google Gemini."""
        import google.generativeai as genai
        
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        response = model.generate_content(prompt)
        
        import json
        return json.loads(response.text)
    
    async def _analyze_with_ollama(self, prompt: str) -> Optional[dict]:
        """Analyze using Ollama."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "format": "json",
                },
                timeout=60,
            )
            
            if response.status_code == 200:
                import json
                return json.loads(response.json().get("response", "{}"))
        
        return None
    
    def _calculate_score(self, flags: List[ScamIndicator]) -> Tuple[int, float]:
        """Calculate final scam score and confidence."""
        if not flags:
            return 0, 0.5
        
        # Weighted sum
        total_weight = sum(f.weight for f in flags)
        max_possible = len(flags) * 100
        
        raw_score = (total_weight / max_possible) * 100
        
        # Boost for critical flags
        critical_flags = [f for f in flags if f.weight >= 80]
        if critical_flags:
            raw_score = max(raw_score, 70 + len(critical_flags) * 10)
        
        scam_score = min(100, int(raw_score))
        
        # Calculate confidence
        if len(flags) > 1:
            weights = [f.weight for f in flags]
            avg_weight = sum(weights) / len(weights)
            variance = sum((w - avg_weight)**2 for w in weights) / len(weights)
            confidence = max(0.5, 1.0 - (variance / 10000))
        else:
            confidence = 0.6
        
        return scam_score, round(confidence, 2)
    
    def _get_risk_level(self, score: int) -> str:
        """Get risk level from score."""
        if score <= 30:
            return "low"
        elif score <= 50:
            return "medium"
        elif score <= 70:
            return "high"
        else:
            return "critical"
    
    async def _save_result(self, job_data: dict, result: dict):
        """Save scam analysis result to database."""
        try:
            job_url = job_data.get("url")
            if not job_url:
                return
            
            # Find or create job
            job = await self.job_repo.get_by_url(job_url)
            if not job:
                return
            
            # Create or update scam score
            scam_score = ScamScore(
                job_id=job.id,
                scam_score=result["scam_score"],
                confidence=result["confidence"],
                is_scam=result["is_scam"],
                flags=result["flags"],
                reasons=result["reasons"],
                analyzed_at=datetime.now(timezone.utc),
            )
            
            self.session.add(scam_score)
            await self.session.flush()
        
        except Exception as e:
            logger.error(f"Failed to save scam result: {e}")
```

---

## Scam Report

```python
async def generate_scam_report(self, days: int = 7) -> dict:
    """Generate scam detection report."""
    from sqlalchemy import func, select
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Total analyzed
    total_query = select(func.count(ScamScore.id)).where(
        ScamScore.analyzed_at >= cutoff
    )
    total = (await self.session.execute(total_query)).scalar() or 0
    
    # Scams detected
    scam_query = select(func.count(ScamScore.id)).where(
        ScamScore.analyzed_at >= cutoff,
        ScamScore.is_scam == True
    )
    scams = (await self.session.execute(scam_query)).scalar() or 0
    
    # Average score
    avg_query = select(func.avg(ScamScore.scam_score)).where(
        ScamScore.analyzed_at >= cutoff
    )
    avg_score = (await self.session.execute(avg_query)).scalar() or 0
    
    return {
        "period_days": days,
        "total_analyzed": total,
        "scams_detected": scams,
        "scam_rate": round(scams / total * 100, 2) if total > 0 else 0,
        "average_score": round(avg_score, 2),
    }
```

---

## Metrics & Monitoring

| Metric | Description |
|--------|-------------|
| `scam_total_analyzed` | Total jobs analyzed |
| `scam_detected_total` | Scams detected |
| `scam_score_average` | Average scam score |
| `scam_detection_rate` | Percentage detected |
| `scam_false_positive_rate` | False positive rate |
| `scam_analysis_duration_seconds` | Analysis time |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 11: AI Classification](./11-ai-classification.md)
