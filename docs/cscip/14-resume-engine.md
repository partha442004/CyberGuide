# CyberShield Career Intelligence Platform (CSCIP) - Resume Engine

## Overview

The Resume Engine analyzes resumes, extracts skills/experience, and matches against job opportunities. It provides ATS scoring, skill gap analysis, and improvement suggestions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       RESUME ENGINE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: Resume (PDF/DOCX)                                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PROCESSING PIPELINE                               │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │  │  Parse   │───▶│ Extract  │───▶│  Match   │───▶│  Score   │     │   │
│  │  │  Resume  │    │  Data    │    │  Jobs    │    │  Resume  │     │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                      │   │
│  │  │ Generate │───▶│  Improve │───▶│  Report  │                      │   │
│  │  │ Insights │    │  Tips    │    │  Results │                      │   │
│  │  └──────────┘    └──────────┘    └──────────┘                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Output: ResumeAnalysis                                                     │
│  {                                                                          │
│    "skills": [...],                                                        │
│    "education": [...],                                                     │
│    "experience": [...],                                                    │
│    "projects": [...],                                                      │
│    "certifications": [...],                                                │
│    "ats_score": 78.5,                                                      │
│    "match_results": [...],                                                 │
│    "suggestions": [...]                                                    │
│  }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Code

```python
# src/cybershield/resume/parser.py

import re
from typing import Any, Dict, List, Optional
from pathlib import Path


class ResumeParser:
    """Parse resume files (PDF/DOCX)."""
    
    async def parse(self, file_path: str) -> Dict[str, Any]:
        """Parse resume and extract structured data."""
        path = Path(file_path)
        
        if path.suffix.lower() == ".pdf":
            text = await self._parse_pdf(file_path)
        elif path.suffix.lower() in [".docx", ".doc"]:
            text = await self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        return {
            "raw_text": text,
            "skills": self._extract_skills(text),
            "education": self._extract_education(text),
            "experience": self._extract_experience(text),
            "projects": self._extract_projects(text),
            "certifications": self._extract_certifications(text),
            "contact": self._extract_contact(text),
        }
    
    async def _parse_pdf(self, file_path: str) -> str:
        """Parse PDF file."""
        import PyPDF2
        
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    async def _parse_docx(self, file_path: str) -> str:
        """Parse DOCX file."""
        from docx import Document
        
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text."""
        # Common cybersecurity skills
        skill_patterns = [
            "python", "javascript", "sql", "linux", "windows",
            "splunk", "siem", "wireshark", "nmap", "burp suite",
            "metasploit", "nessus", "owasp", "渗透测试", "penetration testing",
            "incident response", "forensics", "malware analysis",
            "aws", "azure", "gcp", "docker", "kubernetes",
            "git", "ci/cd", "terraform", "ansible",
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        for skill in skill_patterns:
            if skill in text_lower:
                found_skills.append(skill)
        
        return list(set(found_skills))
    
    def _extract_education(self, text: str) -> List[Dict[str, str]]:
        """Extract education information."""
        education = []
        
        # Simple pattern matching
        patterns = [
            r"(Bachelor|Master|PhD|B\.?S\.?|M\.?S\.?|B\.?Tech|M\.?Tech).*?(?:in|of)\s+(.*?)(?:\n|$)",
            r"(B\.?E\.?|M\.?E\.?)\s+(?:in\s+)?(.*?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                education.append({
                    "degree": match.group(1).strip(),
                    "field": match.group(2).strip() if match.group(2) else "",
                })
        
        return education
    
    def _extract_experience(self, text: str) -> List[Dict[str, str]]:
        """Extract work experience."""
        experience = []
        
        # Look for experience section
        exp_section = re.search(
            r"(?:experience|work history|employment).*?\n(.*?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        
        if exp_section:
            # Extract job titles and companies
            job_pattern = r"(.+?)\s+(?:at|@)\s+(.+?)(?:\n|$)"
            for match in re.finditer(job_pattern, exp_section.group(1)):
                experience.append({
                    "title": match.group(1).strip(),
                    "company": match.group(2).strip(),
                })
        
        return experience
    
    def _extract_projects(self, text: str) -> List[str]:
        """Extract projects."""
        projects = []
        
        proj_section = re.search(
            r"(?:projects|portfolio).*?\n(.*?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        
        if proj_section:
            lines = proj_section.group(1).split("\n")
            for line in lines:
                line = line.strip()
                if line and len(line) > 10:
                    projects.append(line)
        
        return projects
    
    def _extract_certifications(self, text: str) -> List[str]:
        """Extract certifications."""
        cert_patterns = [
            "CEH", "OSCP", "CISSP", "CompTIA Security+", "AWS Certified",
            "Azure Certified", "GCP Certified", "GIAC", "CISM", "CISA",
        ]
        
        found_certs = []
        text_upper = text.upper()
        
        for cert in cert_patterns:
            if cert.upper() in text_upper:
                found_certs.append(cert)
        
        return found_certs
    
    def _extract_contact(self, text: str) -> Dict[str, str]:
        """Extract contact information."""
        contact = {}
        
        # Email
        email_match = re.search(r"[\w.-]+@[\w.-]+\.\w+", text)
        if email_match:
            contact["email"] = email_match.group()
        
        # Phone
        phone_match = re.search(r"[\+]?[\d\-\(\)]{10,}", text)
        if phone_match:
            contact["phone"] = phone_match.group()
        
        # LinkedIn
        linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", text)
        if linkedin_match:
            contact["linkedin"] = f"https://{linkedin_match.group()}"
        
        # GitHub
        github_match = re.search(r"github\.com/[\w-]+", text)
        if github_match:
            contact["github"] = f"https://{github_match.group()}"
        
        return contact
```

---

## Resume Scorer

```python
# src/cybershield/resume/scorer.py

from typing import Any, Dict, List


class ResumeScorer:
    """Score resume for ATS compatibility."""
    
    # ATS scoring criteria
    CRITERIA = {
        "contact_info": {"weight": 10, "description": "Contact information present"},
        "skills_section": {"weight": 15, "description": "Skills section exists"},
        "experience_section": {"weight": 20, "description": "Work experience present"},
        "education_section": {"weight": 10, "description": "Education section present"},
        "keywords_match": {"weight": 25, "description": "Keywords match job description"},
        "formatting": {"weight": 10, "description": "Clean formatting"},
        "length": {"weight": 10, "description": "Appropriate length"},
    }
    
    def calculate_ats_score(
        self,
        resume_data: Dict[str, Any],
        job_keywords: List[str] = None,
    ) -> Dict[str, Any]:
        """Calculate ATS compatibility score."""
        scores = {}
        
        # Contact info
        scores["contact_info"] = 100 if resume_data.get("contact") else 0
        
        # Skills section
        scores["skills_section"] = 100 if resume_data.get("skills") else 0
        
        # Experience section
        scores["experience_section"] = 100 if resume_data.get("experience") else 0
        
        # Education section
        scores["education_section"] = 100 if resume_data.get("education") else 0
        
        # Keywords match
        if job_keywords:
            resume_skills = set(s.lower() for s in resume_data.get("skills", []))
            job_skills = set(k.lower() for k in job_keywords)
            matched = resume_skills & job_skills
            scores["keywords_match"] = int((len(matched) / len(job_skills)) * 100) if job_skills else 0
        else:
            scores["keywords_match"] = 50
        
        # Formatting (basic check)
        raw_text = resume_data.get("raw_text", "")
        scores["formatting"] = 100 if len(raw_text) > 100 else 50
        
        # Length (1-2 pages ideal)
        word_count = len(raw_text.split())
        if 300 <= word_count <= 1000:
            scores["length"] = 100
        elif 200 <= word_count <= 1500:
            scores["length"] = 70
        else:
            scores["length"] = 40
        
        # Calculate weighted score
        total_score = 0
        total_weight = 0
        
        for criterion, details in self.CRITERIA.items():
            score = scores.get(criterion, 0)
            weight = details["weight"]
            total_score += score * weight
            total_weight += weight
        
        ats_score = round(total_score / total_weight, 1) if total_weight > 0 else 0
        
        return {
            "ats_score": ats_score,
            "criteria_scores": scores,
            "breakdown": [
                {
                    "criterion": criterion,
                    "score": scores.get(criterion, 0),
                    "weight": details["weight"],
                    "description": details["description"],
                }
                for criterion, details in self.CRITERIA.items()
            ],
        }
```

---

## Resume Matcher

```python
# src/cybershield/resume/matcher.py

from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.domain.models import Job
from cybershield.repositories.job_repository import JobRepository


class ResumeMatcher:
    """Match resume against job opportunities."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)
    
    async def match_resume_to_jobs(
        self,
        resume_data: Dict[str, Any],
        job_ids: List[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Match resume to jobs and return scores."""
        resume_skills = set(s.lower() for s in resume_data.get("skills", []))
        
        # Get jobs to match against
        if job_ids:
            jobs = []
            for job_id in job_ids:
                job = await self.job_repo.get_by_id(job_id)
                if job:
                    jobs.append(job)
        else:
            jobs = await self.job_repo.get_active_jobs(limit=limit)
        
        match_results = []
        
        for job in jobs:
            job_skills = set(
                s.lower() for s in (job.required_skills or [])
            )
            
            if not job_skills:
                continue
            
            # Calculate match
            matched = resume_skills & job_skills
            missing = job_skills - resume_skills
            
            match_percentage = (len(matched) / len(job_skills) * 100) if job_skills else 0
            
            match_results.append({
                "job_id": job.id,
                "job_title": job.title,
                "company": job.company,
                "match_score": round(match_percentage, 1),
                "matched_skills": list(matched),
                "missing_skills": list(missing),
                "total_job_skills": len(job_skills),
                "matched_count": len(matched),
            })
        
        # Sort by match score
        match_results.sort(key=lambda x: x["match_score"], reverse=True)
        
        return match_results[:limit]
    
    def generate_suggestions(
        self,
        resume_data: Dict[str, Any],
        match_results: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate improvement suggestions based on matches."""
        suggestions = []
        
        # Analyze common missing skills
        all_missing = []
        for result in match_results[:5]:
            all_missing.extend(result.get("missing_skills", []))
        
        # Count frequency
        skill_frequency = {}
        for skill in all_missing:
            skill_frequency[skill] = skill_frequency.get(skill, 0) + 1
        
        # Top missing skills
        top_missing = sorted(skill_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
        
        for skill, count in top_missing:
            suggestions.append(
                f"Consider learning {skill} - missing in {count} matching jobs"
            )
        
        # Resume length suggestion
        word_count = len(resume_data.get("raw_text", "").split())
        if word_count < 300:
            suggestions.append("Your resume is quite short. Consider adding more details.")
        elif word_count > 1500:
            suggestions.append("Your resume is long. Consider condensing to 1-2 pages.")
        
        # Skills section suggestion
        if not resume_data.get("skills"):
            suggestions.append("Add a dedicated Skills section to your resume.")
        
        return suggestions
```

---

## API Endpoints

```
POST /api/v1/resume/upload
POST /api/v1/resume/{resume_id}/match
GET  /api/v1/resume/{resume_id}/analysis
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `resume_uploads_total` | Total resumes uploaded |
| `resume_avg_ats_score` | Average ATS score |
| `resume_match_rate` | Average match rate |
| `resume_suggestions_generated` | Suggestions generated |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 15: Deployment](./15-deployment.md)
