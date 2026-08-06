"""
AI-powered Resume Skill Extraction Enhancement

Uses AI to improve skill extraction accuracy from resumes by:
1. Understanding context and context-aware skill detection
2. Extracting skills from project descriptions
3. Identifying implicit skills from experience
4. Mapping synonyms and variations to standard skill names
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Skill synonym mapping for better matching
SKILL_SYNONYMS = {
    # Programming languages
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "ts": "typescript",
    "rb": "ruby",
    "golang": "go",
    "c plus plus": "c++",
    "c sharp": "c#",
    # Security tools
    "metasploit framework": "metasploit",
    "burp": "burp suite",
    "burp professional": "burp suite",
    "nmap scanner": "nmap",
    "wireshark network": "wireshark",
    # Cloud platforms
    "amazon web services": "aws",
    "microsoft azure": "azure",
    "google cloud platform": "gcp",
    "google cloud": "gcp",
    # DevOps tools
    "k8s": "kubernetes",
    "tf": "terraform",
    "ansible automation": "ansible",
    # Security concepts
    "app sec": "application security",
    "appsec": "application security",
    "net sec": "network security",
    "netsec": "network security",
    "info sec": "information security",
    "infosec": "information security",
    "sec ops": "security operations",
    "secops": "security operations",
    "dev sec ops": "devsecops",
    "devsecops": "devsecops",
    # Data tools
    "pd": "pandas",
    "np": "numpy",
    "sklearn": "scikit-learn",
    "sci-kit learn": "scikit-learn",
    # Web frameworks
    "dj": "django",
    "flask framework": "flask",
    "express js": "express",
    "next js": "next.js",
    "vue js": "vue.js",
    "angular js": "angular",
}

# Context-aware skill detection patterns
CONTEXT_PATTERNS = {
    "penetration_testing": [
        (
            r"(?:performed?|conducted?|executed?|carried out?)"
            r"\s+(?:a\s+)?(?:penetration|pen|vulnerability)"
            r"\s+(?:test|assessment)"
        ),
        r"(?:found|discovered|identified)\s+(?:a\s+)?(?:vulnerability|weakness|flaw)",
        r"(?:exploited?|exploitation)\s+(?:a\s+)?(?:vulnerability|weakness|flaw)",
        r"(?:red team|blue team|purple team)\s+(?:exercise|operation|activity)",
    ],
    "soc_analyst": [
        (
            r"(?:monitored?|analyzed?|investigated?)"
            r"\s+(?:security|siem|log|alert)"
        ),
        r"(?:incident|security incident)\s+(?:response|handling|management)",
        (
            r"(?:siem|splunk|sentinel|qradar)"
            r"\s+(?:dashboard|query|analysis)"
        ),
    ],
    "malware_analysis": [
        (
            r"(?:analyzed?|reverse engineered?|dissected?)"
            r"\s+(?:malware|virus|trojan|ransomware)"
        ),
        r"(?:dynamic|static)\s+(?:analysis|reverse engineering)",
        r"(?:sandbox|virustotal|any\.run)\s+(?:analysis|detonation)",
    ],
    "cloud_security": [
        r"(?:configured?|implemented?|secured?)\s+(?:aws|azure|gcp|cloud)\s+(?:security|iam|policy)",
        (
            r"(?:s3|ec2|lambda|iam|guardduty|security hub)"
            r"\s+(?:configuration|hardening|audit)"
        ),
    ],
}


class AIResumeEnhancer:
    """AI-powered resume enhancement for better skill extraction."""

    def __init__(self):
        self._all_skills = self._load_skill_database()

    def _load_skill_database(self) -> dict[str, str]:
        """Load comprehensive skill database."""
        from cybershield.services.resume_service import SECURITY_SKILLS

        skills = {}
        for category, skill_list in SECURITY_SKILLS.items():
            for skill in skill_list:
                skills[skill.lower()] = category
        return skills

    def enhance_skill_extraction(
        self, text: str, basic_skills: list[dict]
    ) -> list[dict]:
        """Enhance basic skill extraction with AI-powered context analysis."""
        enhanced_skills = list(basic_skills)
        seen_skills = {s["name"].lower() for s in enhanced_skills}

        # 1. Extract skills from context patterns
        context_skills = self._extract_context_skills(text)
        for skill in context_skills:
            if skill["name"].lower() not in seen_skills:
                enhanced_skills.append(skill)
                seen_skills.add(skill["name"].lower())

        # 2. Extract skills from synonyms
        synonym_skills = self._extract_synonym_skills(text)
        for skill in synonym_skills:
            if skill["name"].lower() not in seen_skills:
                enhanced_skills.append(skill)
                seen_skills.add(skill["name"].lower())

        # 3. Extract implicit skills from experience descriptions
        implicit_skills = self._extract_implicit_skills(text)
        for skill in implicit_skills:
            if skill["name"].lower() not in seen_skills:
                enhanced_skills.append(skill)
                seen_skills.add(skill["name"].lower())

        # 4. Boost confidence for skills mentioned multiple times
        return self._boost_confidence(enhanced_skills, text)

    def _extract_context_skills(self, text: str) -> list[dict]:
        """Extract skills based on context patterns."""
        skills: list[dict[str, Any]] = []
        text_lower = text.lower()

        for category, patterns in CONTEXT_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    # Extract the skill from the matched context
                    skill_name = self._infer_skill_from_context(match.group(), category)
                    if skill_name and skill_name not in [
                        s["name"].lower() for s in skills
                    ]:
                        skills.append(
                            {
                                "name": skill_name.title(),
                                "category": category,
                                "confidence": 0.85,
                                "source": "context_analysis",
                            }
                        )

        return skills

    def _infer_skill_from_context(self, context: str, category: str) -> str | None:
        """Infer skill name from context."""
        context_lower = context.lower()

        # Map category to likely skills
        category_skills = {
            "penetration_testing": [
                "penetration testing",
                "vulnerability assessment",
                "ethical hacking",
            ],
            "soc_analyst": ["soc", "siem", "incident response", "log analysis"],
            "malware_analysis": [
                "malware analysis",
                "reverse engineering",
                "forensics",
            ],
            "cloud_security": [
                "cloud security",
                "aws security",
                "azure security",
                "gcp security",
            ],
        }

        skills = category_skills.get(category, [])
        for skill in skills:
            if skill in context_lower:
                return skill

        return None

    def _extract_synonym_skills(self, text: str) -> list[dict]:
        """Extract skills using synonym mapping."""
        skills: list[dict[str, Any]] = []
        text_lower = text.lower()

        for synonym, standard_name in SKILL_SYNONYMS.items():
            if synonym in text_lower and standard_name not in [
                s["name"].lower() for s in skills
            ]:
                # Find the category for this skill
                category = self._all_skills.get(standard_name, "general")
                skills.append(
                    {
                        "name": standard_name.title(),
                        "category": category,
                        "confidence": 0.8,
                        "source": "synonym_mapping",
                    }
                )

        return skills

    def _extract_implicit_skills(self, text: str) -> list[dict]:
        """Extract implicit skills from experience descriptions."""
        skills: list[dict[str, Any]] = []
        text_lower = text.lower()

        # Patterns that indicate skills without explicit mention
        implicit_patterns = {
            "python": [
                r"(?:wrote|developed|built|created|automated?)\s+(?:a\s+)?(?:script|tool|automation|bot)",
                r"(?:scripting|automation)\s+(?:with|using)\s+python",
            ],
            "linux": [
                r"(?:managed?|administered?|configured?)\s+(?:linux|unix|server)",
                r"(?:bash|shell)\s+(?:scripting|commands)",
            ],
            "sql": [
                r"(?:queried?|extracted?|analyzed?)\s+(?:data|information)\s+(?:from|using)\s+(?:sql|database)",
                r"(?:database|sql)\s+(?:queries|querying|management)",
            ],
            "git": [
                (
                    r"(?:version control|git|github|gitlab)"
                    r"\s+(?:experience|knowledge|usage)"
                ),
                (
                    r"(?:committed?|pushed?|merged?)"
                    r"\s+(?:code|changes)\s+(?:to|in)"
                    r"\s+(?:git|github)"
                ),
            ],
        }

        for skill, patterns in implicit_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    category = self._all_skills.get(skill, "general")
                    if skill not in [s["name"].lower() for s in skills]:
                        skills.append(
                            {
                                "name": skill.title(),
                                "category": category,
                                "confidence": 0.75,
                                "source": "implicit_detection",
                            }
                        )
                    break

        return skills

    def _boost_confidence(self, skills: list[dict], text: str) -> list[dict]:
        """Boost confidence for skills mentioned multiple times."""
        text_lower = text.lower()

        for skill in skills:
            skill_name = skill["name"].lower()
            # Count occurrences
            count = text_lower.count(skill_name)
            if count >= 3:
                skill["confidence"] = min(0.95, skill["confidence"] + 0.1)
                skill["mention_count"] = count
            elif count >= 2:
                skill["confidence"] = min(0.9, skill["confidence"] + 0.05)
                skill["mention_count"] = count
            else:
                skill["mention_count"] = count

        return skills

    def extract_experience_level(self, text: str) -> str:
        """Extract experience level from resume text."""
        text_lower = text.lower()

        # Experience level indicators
        indicators = {
            "senior": [
                r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
                r"senior\s+(?:engineer|developer|analyst|architect)",
                r"lead\s+(?:engineer|developer|analyst)",
                r"principal\s+(?:engineer|developer|analyst)",
                r"staff\s+(?:engineer|developer|analyst)",
            ],
            "mid": [
                r"(\d+)\s*-\s*(\d+)\s*years?\s+(?:of\s+)?experience",
                r"mid[- ]level",
                r"intermediate",
            ],
            "junior": [
                r"junior\s+(?:engineer|developer|analyst)",
                r"entry[- ]level",
                r"fresher",
                r"(\d)\s*(?:to|-)\s*(\d)\s*years?\s+(?:of\s+)?experience",
            ],
        }

        for level, patterns in indicators.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Check if it's a year pattern
                    if r"(\d+)" in pattern:
                        years = int(match.group(1))
                        if years >= 5:
                            return "senior"
                        if years >= 2:
                            return "mid"
                        return "junior"
                    return level

        return "unknown"

    def extract_preferred_roles(self, text: str) -> list[str]:
        """Extract preferred roles from resume objective/summary."""
        roles = []
        text_lower = text.lower()

        # Role keywords
        role_patterns = [
            (
                (
                    r"(?:seeking|looking for|interested in|pursuing)"
                    r"\s+(?:a\s+)?(.*?)"
                    r"(?:\s+position|\s+role|\s+job|\s+career|\.|,|$)"
                ),
                1,
            ),
            (r"(?:objective|summary|profile)[:\s]+(.*?)(?:\n|$)", 1),
        ]

        for pattern, group in role_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                role_text = match.group(group).strip()
                # Extract role titles
                role_titles = [
                    "security analyst",
                    "soc analyst",
                    "penetration tester",
                    "security engineer",
                    "security architect",
                    "security consultant",
                    "malware analyst",
                    "forensics analyst",
                    "incident responder",
                    "cloud security engineer",
                    "application security engineer",
                    "network security engineer",
                    "security auditor",
                ]
                for role in role_titles:
                    if role in role_text and role not in roles:
                        roles.append(role)

        return roles[:5]  # Return top 5 roles


def enhance_resume_parsing(text: str, basic_skills: list[dict]) -> dict[str, Any]:
    """Main function to enhance resume parsing with AI."""
    enhancer = AIResumeEnhancer()

    # Enhance skills
    enhanced_skills = enhancer.enhance_skill_extraction(text, basic_skills)

    # Extract additional info
    experience_level = enhancer.extract_experience_level(text)
    preferred_roles = enhancer.extract_preferred_roles(text)

    return {
        "skills": enhanced_skills,
        "experience_level": experience_level,
        "preferred_roles": preferred_roles,
        "total_skills": len(enhanced_skills),
        "high_confidence_skills": len(
            [s for s in enhanced_skills if s.get("confidence", 0) >= 0.85]
        ),
    }
