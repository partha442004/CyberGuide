# CyberShield Career Intelligence Platform (CSCIP) - AI Classification Engine

## Overview

The AI Classification Engine categorizes jobs using AI/ML models and rule-based fallbacks. It extracts skills, determines job types, experience levels, and assigns security domain categories.

---

## Classification Categories

### Job Types
```python
class JobType(str, Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    REMOTE = "remote"
    GRADUATE_PROGRAM = "graduate_program"
    WALK_IN = "walk_in"
    OFF_CAMPUS = "off_campus"
    GOVERNMENT = "government"
    UNKNOWN = "unknown"
```

### Experience Levels
```python
class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"
    INTERN = "intern"
    FRESHER = "fresher"
    UNKNOWN = "unknown"
```

### Security Domains
```python
class SecurityDomain(str, Enum):
    SOC = "soc"
    BLUE_TEAM = "blue_team"
    RED_TEAM = "red_team"
    PURPLE_TEAM = "purple_team"
    PENETRATION_TESTING = "penetration_testing"
    MALWARE_ANALYSIS = "malware_analysis"
    INCIDENT_RESPONSE = "incident_response"
    DIGITAL_FORENSICS = "digital_forensics"
    THREAT_INTELLIGENCE = "threat_intelligence"
    CLOUD_SECURITY = "cloud_security"
    APPLICATION_SECURITY = "application_security"
    NETWORK_SECURITY = "network_security"
    DEVSECOPS = "devsecops"
    GRC = "grc"
    IAM = "iam"
    AI_SECURITY = "ai_security"
    GENERAL = "general"
```

---

## Classification Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLASSIFICATION PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: Raw Job Data                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 1: AI Classification (Primary)                                │   │
│  │  • Send to Ollama/Gemini for classification                         │   │
│  │  • Get structured response with all categories                      │   │
│  │  • Confidence score from AI                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 2: Rule-Based Classification (Fallback)                       │   │
│  │  • Pattern matching for job type                                    │   │
│  │  • Keyword matching for security domain                             │   │
│  │  • Experience level detection                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 3: Skill Extraction                                           │   │
│  │  • Extract required skills from description                         │   │
│  │  • Extract preferred skills                                         │   │
│  │  • Match against skill database                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 4: Enrichment                                                 │   │
│  │  • Salary estimation (if missing)                                   │   │
│  │  • Location normalization                                           │   │
│  │  • Company categorization                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Output: ClassificationResult                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Code

```python
# src/cybershield/engines/classification.py

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.config import get_settings
from cybershield.domain.enums import JobType, ExperienceLevel, SecurityDomain, SkillCategory
from cybershield.repositories.skill_repository import SkillRepository
from cybershield.services.ai_service import AIService
from cybershield.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ClassificationEngine:
    """Engine for classifying and categorizing jobs."""
    
    # Skill keywords for extraction
    SKILL_KEYWORDS = {
        "programming": [
            "python", "javascript", "typescript", "java", "c++", "go", "rust",
            "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "bash",
        ],
        "frameworks": [
            "react", "vue", "angular", "django", "flask", "fastapi", "express",
            "spring", "rails", "laravel", "nextjs", "node.js", ".net",
        ],
        "security_tools": [
            "splunk", "siem", "sentinel", "qradar", "elastic", "wireshark",
            "nmap", "burp suite", "metasploit", "nessus", "qualys", "rapid7",
            "crowdstrike", "palo alto", "fortinet", "checkpoint", "snort",
            "suricata", "yara", "sigma", "mitre att&ck",
        ],
        "cloud_platforms": [
            "aws", "azure", "gcp", "google cloud", "amazon web services",
            "kubernetes", "docker", "terraform", "ansible", "cloudformation",
        ],
        "security_concepts": [
            "owasp", "渗透测试", "penetration testing", "vulnerability assessment",
            "incident response", "forensics", "malware analysis", "reverse engineering",
            "threat hunting", "threat intelligence", "soc", "blue team", "red team",
            "purple team", "devsecops", "zero trust", "iam", "compliance", "grc",
        ],
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_repo = SkillRepository(session)
        self.ai_service = AIService(session)
    
    async def classify_job(self, job_data: dict) -> Dict[str, Any]:
        """Classify a job posting."""
        # Try AI classification first
        classification = await self.ai_service.classify_job(job_data)
        
        # Fall back to rule-based if AI fails
        if "error" in classification:
            classification = self._rule_based_classify(job_data)
        
        # Extract and match skills
        skills = await self._extract_skills(
            classification.get("skills", []),
            job_data.get("description", ""),
        )
        
        return {
            **classification,
            "matched_skills": skills,
        }
    
    def _rule_based_classify(self, job_data: dict) -> Dict[str, Any]:
        """Rule-based classification fallback."""
        title = job_data.get("title", "").lower()
        description = job_data.get("description", "").lower()
        text = f"{title} {description}"
        
        # Determine job type
        job_type = self._detect_job_type(title, description)
        
        # Determine experience level
        experience = self._detect_experience_level(title, description)
        
        # Determine security domain
        domain = self._detect_security_domain(text)
        
        # Extract skills
        skills = self._extract_skills_from_text(text)
        
        # Detect remote
        is_remote = any(word in text for word in ["remote", "work from home", "wfh"])
        
        return {
            "job_type": job_type.value,
            "experience_level": experience.value,
            "security_domain": domain.value,
            "skills": skills,
            "is_remote": is_remote,
            "confidence": 0.6,
        }
    
    def _detect_job_type(self, title: str, description: str) -> JobType:
        """Detect job type from title and description."""
        text = f"{title} {description}".lower()
        
        if any(word in text for word in ["intern", "internship", "trainee"]):
            return JobType.INTERNSHIP
        elif any(word in text for word in ["full time", "full-time", "permanent"]):
            return JobType.FULL_TIME
        elif any(word in text for word in ["part time", "part-time"]):
            return JobType.PART_TIME
        elif any(word in text for word in ["contract", "freelance", "consultant"]):
            return JobType.CONTRACT
        elif any(word in text for word in ["remote", "work from home"]):
            return JobType.REMOTE
        elif any(word in text for word in ["graduate", "trainee", "entry level"]):
            return JobType.GRADUATE_PROGRAM
        elif any(word in text for word in ["walk in", "walk-in"]):
            return JobType.WALK_IN
        elif any(word in text for word in ["government", "govt", "psu"]):
            return JobType.GOVERNMENT
        
        return JobType.UNKNOWN
    
    def _detect_experience_level(self, title: str, description: str) -> ExperienceLevel:
        """Detect experience level."""
        text = f"{title} {description}".lower()
        
        if any(word in text for word in ["senior", "lead", "principal", "staff"]):
            return ExperienceLevel.SENIOR
        elif any(word in text for word in ["junior", "entry", "associate", "fresher"]):
            return ExperienceLevel.JUNIOR
        elif any(word in text for word in ["mid level", "intermediate", "3-5 years"]):
            return ExperienceLevel.MID
        elif any(word in text for word in ["intern", "internship"]):
            return ExperienceLevel.INTERN
        elif any(word in text for word in ["fresher", "fresh graduate", "0-1 years"]):
            return ExperienceLevel.FRESHER
        elif any(word in text for word in ["executive", "director", "vp", "head"]):
            return ExperienceLevel.EXECUTIVE
        
        return ExperienceLevel.UNKNOWN
    
    def _detect_security_domain(self, text: str) -> SecurityDomain:
        """Detect security domain from text."""
        domain_keywords = {
            SecurityDomain.SOC: ["soc", "security operations", "security analyst"],
            SecurityDomain.BLUE_TEAM: ["blue team", "defensive", "detection"],
            SecurityDomain.RED_TEAM: ["red team", "offensive", "penetration"],
            SecurityDomain.PURPLE_TEAM: ["purple team"],
            SecurityDomain.PENETRATION_TESTING: ["penetration testing", "pen test", "vapt"],
            SecurityDomain.MALWARE_ANALYSIS: ["malware", "reverse engineering", "vt"],
            SecurityDomain.INCIDENT_RESPONSE: ["incident response", "ir", "dfir"],
            SecurityDomain.DIGITAL_FORENSICS: ["forensics", "digital forensics"],
            SecurityDomain.THREAT_INTELLIGENCE: ["threat intelligence", "threat hunting"],
            SecurityDomain.CLOUD_SECURITY: ["cloud security", "aws security", "azure security"],
            SecurityDomain.APPLICATION_SECURITY: ["application security", "appsec", "sast", "dast"],
            SecurityDomain.NETWORK_SECURITY: ["network security", "firewall", "ids", "ips"],
            SecurityDomain.DEVSECOPS: ["devsecops", "security automation"],
            SecurityDomain.GRC: ["grc", "compliance", "audit", "risk"],
            SecurityDomain.IAM: ["iam", "identity", "access management"],
            SecurityDomain.AI_SECURITY: ["ai security", "ml security", "llm security"],
        }
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in text for keyword in keywords):
                return domain
        
        return SecurityDomain.GENERAL
    
    async def _extract_skills(self, ai_skills: List[str], description: str) -> List[Dict[str, Any]]:
        """Extract and categorize skills from job."""
        skills = []
        
        # Process AI-detected skills
        for skill_name in ai_skills:
            skill = await self.skill_repo.create_or_get(
                skill_name.lower(),
                self._categorize_skill(skill_name),
            )
            skills.append({
                "id": skill.id,
                "name": skill.name,
                "category": skill.category.value,
            })
        
        # Also extract from description using patterns
        pattern_skills = self._extract_skills_from_text(description)
        for skill_name in pattern_skills:
            if not any(s["name"] == skill_name.lower() for s in skills):
                skill = await self.skill_repo.create_or_get(
                    skill_name.lower(),
                    self._categorize_skill(skill_name),
                )
                skills.append({
                    "id": skill.id,
                    "name": skill.name,
                    "category": skill.category.value,
                })
        
        return skills
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skills from text using pattern matching."""
        found_skills = []
        text_lower = text.lower()
        
        for category, skills in self.SKILL_KEYWORDS.items():
            for skill in skills:
                if skill in text_lower:
                    found_skills.append(skill)
        
        return list(set(found_skills))
    
    def _categorize_skill(self, skill_name: str) -> SkillCategory:
        """Categorize a skill by name."""
        skill_lower = skill_name.lower()
        
        if skill_lower in self.SKILL_KEYWORDS.get("programming", []):
            return SkillCategory.PROGRAMMING
        elif skill_lower in self.SKILL_KEYWORDS.get("frameworks", []):
            return SkillCategory.FRAMEWORK
        elif skill_lower in self.SKILL_KEYWORDS.get("security_tools", []):
            return SkillCategory.TOOL
        elif skill_lower in self.SKILL_KEYWORDS.get("cloud_platforms", []):
            return SkillCategory.TOOL
        else:
            return SkillCategory.DOMAIN_KNOWLEDGE
    
    async def get_skill_demand(self) -> List[Dict[str, Any]]:
        """Get skill demand statistics from job listings."""
        from sqlalchemy import func, select
        from cybershield.domain.models import Skill, JobSkill, Job
        
        query = (
            select(
                Skill.name,
                Skill.category,
                func.count(JobSkill.job_id).label("demand")
            )
            .join(JobSkill, Skill.id == JobSkill.skill_id)
            .join(Job, JobSkill.job_id == Job.id)
            .where(Job.is_active == True)
            .group_by(Skill.id)
            .order_by(func.count(JobSkill.job_id).desc())
            .limit(20)
        )
        
        result = await self.session.execute(query)
        return [
            {
                "skill": row.name,
                "category": row.category.value,
                "demand": row.demand,
            }
            for row in result.all()
        ]
```

---

## AI Classification Prompt

```python
CLASSIFICATION_PROMPT = """Classify this cybersecurity job posting and return JSON with:

{{
    "job_type": "internship|full_time|part_time|contract|remote|graduate_program",
    "experience_level": "entry|junior|mid|senior|lead|intern|fresher",
    "security_domain": "soc|blue_team|red_team|penetration_testing|malware_analysis|incident_response|cloud_security|application_security|devsecops|grc|general",
    "skills": ["list", "of", "extracted", "skills"],
    "is_remote": true/false,
    "confidence": 0.0-1.0
}}

Job Title: {title}
Company: {company}
Description: {description[:1000]}
Location: {location}
Salary: {salary_min} - {salary_max}

Respond only with valid JSON."""
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `classification_total` | Total jobs classified |
| `classification_accuracy` | AI classification accuracy |
| `skill_extraction_rate` | Skills successfully extracted |
| `domain_detection_rate` | Security domain detection rate |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 12: Notification Engine](./12-notification-engine.md)
