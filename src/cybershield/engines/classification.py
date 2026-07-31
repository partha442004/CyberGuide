"""
Classification Engine

Classifies jobs into categories and extracts skills using:
- Keyword-based classification
- Pattern matching
- Skill database matching
- Experience level detection
"""

import re
import logging
from typing import Any, Dict, List, Optional, Set

from cybershield.engines.base import BaseEngine, EngineResult

logger = logging.getLogger(__name__)


class ClassificationEngine(BaseEngine):
    """
    Classification engine for job listings.

    Handles:
    1. Job type classification (internship, full-time, etc.)
    2. Experience level detection
    3. Security domain classification
    4. Skill extraction and normalization
    """

    # Job type patterns
    JOB_TYPE_PATTERNS = {
        "internship": [
            r"\bintern(?:ship)?\b", r"\btrainee\b", r"\bco-op\b", r"\bapprentice\b",
        ],
        "full_time": [
            r"\bfull[- ]?time\b", r"\bpermanent\b", r"\bregular\b", r"\bemployee\b",
        ],
        "part_time": [
            r"\bpart[- ]?time\b", r"\bfreelance\b", r"\bcontract(?:or)?\b",
        ],
        "contract": [
            r"\bcontract\b", r"\btemporary\b", r"\btemp\b", r"\bconsultant\b",
        ],
        "remote": [
            r"\bremote\b", r"\bwork from home\b", r"\bwfh\b", r"\bdistributed\b",
        ],
    }

    # Experience level patterns
    EXPERIENCE_PATTERNS = {
        "fresher": [
            r"\bfresher\b", r"\b0[- ]?(?:to|-)?\s*1\s*(?:year|yr|y)\b",
            r"\bno experience\b", r"\brecent graduate\b", r"\bentry[- ]?level\b",
        ],
        "junior": [
            r"\bjunior\b", r"\b0[- ]?(?:to|-)?\s*2\s*(?:year|yr|y)\b",
            r"\b1[- ]?(?:to|-)?\s*3\s*(?:year|yr|y)\b",
        ],
        "mid": [
            r"\bmid[- ]?level\b", r"\b3[- ]?(?:to|-)?\s*5\s*(?:year|yr|y)\b",
            r"\bintermediate\b",
        ],
        "senior": [
            r"\bsenior\b", r"\blead\b", r"\b5\+?\s*(?:year|yr|y)\b",
            r"\bexperienced\b", r"\bexpert\b",
        ],
        "intern": [
            r"\bintern\b", r"\binternship\b", r"\btraining\b",
        ],
    }

    # Security domain classifications
    SECURITY_DOMAINS = {
        "SOC": [
            r"\bsoc\b", r"\bsecurity operations\b", r"\bsiem\b",
            r"\bsecurity operations center\b",
        ],
        "Blue Team": [
            r"\bblue team\b", r"\bdefensive\b", r"\bdefense\b",
            r"\bmonitoring\b", r"\bdetection\b",
        ],
        "Red Team": [
            r"\bred team\b", r"\boffensive\b", r"\battack\b",
            r"\bpenetration testing\b", r"\bpentest\b",
        ],
        "Purple Team": [
            r"\bpurple team\b", r"\bcombined\b",
        ],
        "Cloud Security": [
            r"\bcloud security\b", r"\baws security\b", r"\bazure security\b",
            r"\bgcp security\b", r"\bcloud infrastructure\b",
        ],
        "Application Security": [
            r"\bappsec\b", r"\bapplication security\b", r"\bweb security\b",
            r"\bapi security\b", r"\bsecure coding\b",
        ],
        "DevSecOps": [
            r"\bdevsecops\b", r"\bsecurity automation\b", r"\bci\/cd security\b",
            r"\bshift left\b", r"\bsecurity pipeline\b",
        ],
        "Incident Response": [
            r"\bincident response\b", r"\biri\b", r"\bforensic\b",
            r"\bdigital forensic\b", r"\binvestigation\b",
        ],
        "Threat Intelligence": [
            r"\bthreat intelligence\b", r"\bthreat hunting\b",
            r"\bthreat analysis\b", r"\bcti\b",
        ],
        "Malware Analysis": [
            r"\bmalware analysis\b", r"\breverse engineering\b",
            r"\bmalware\b", r"\bsandboxing\b",
        ],
        "GRC": [
            r"\bgrc\b", r"\bgovernance\b", r"\bcompliance\b",
            r"\brisk\b", r"\baudit\b", r"\bregulatory\b",
        ],
        "IAM": [
            r"\biam\b", r"\bidentity\b", r"\baccess management\b",
            r"\bprivileged\b", r"\bauthentication\b",
        ],
        "Network Security": [
            r"\bnetwork security\b", r"\bfirewall\b", r"\bintrusion detection\b",
            r"\bnids\b", r"\bnips\b",
        ],
    }

    # Common cybersecurity skills
    SKILL_DATABASE = {
        # Programming Languages
        "Python": [r"\bpython\b"],
        "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\bnode\.?js\b"],
        "Go": [r"\bgolang\b", r"\bgo(?:lang)?\s+(?:programming|language|developer)\b"],
        "Rust": [r"\brust\b"],
        "PowerShell": [r"\bpowershell\b"],
        "Bash": [r"\bbash\b", r"\bshell scripting\b"],
        "SQL": [r"\bsql\b", r"\bmysql\b", r"\bpostgresql\b"],

        # Security Tools
        "Nmap": [r"\bnmap\b"],
        "Burp Suite": [r"\bburp\b", r"\bburp suite\b"],
        "Wireshark": [r"\bwireshark\b"],
        "Metasploit": [r"\bmetasploit\b"],
        "Nessus": [r"\bnessus\b"],
        "Splunk": [r"\bsplunk\b"],
        "SIEM": [r"\bsiem\b"],
        "Microsoft Sentinel": [r"\bsentinel\b", r"\bmicrosoft sentinel\b"],
        "Elastic": [r"\belastic\b", r"\belk\b", r"\belasticsearch\b"],

        # Cloud Platforms
        "AWS": [r"\baws\b", r"\bamazon web services\b"],
        "Azure": [r"\bazure\b", r"\bmicrosoft azure\b"],
        "GCP": [r"\bgcp\b", r"\bgoogle cloud\b"],
        "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
        "Docker": [r"\bdocker\b", r"\bcontainerization\b"],

        # Security Concepts
        "OWASP": [r"\bowasp\b"],
        "MITRE ATT&CK": [r"\bmitre\b", r"\batt&ck\b", r"\battack framework\b"],
        "Zero Trust": [r"\bzero trust\b"],
        "Cryptography": [r"\bcryptography\b", r"\bencryption\b", r"\bPKI\b"],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("classification", config)

    def _classify_job_type(self, text: str) -> Dict[str, Any]:
        """Classify job type from text."""
        text_lower = text.lower()
        scores = {}

        for job_type, patterns in self.JOB_TYPE_PATTERNS.items():
            score = sum(1 for pattern in patterns if re.search(pattern, text_lower))
            if score > 0:
                scores[job_type] = score

        if not scores:
            return {"type": "full_time", "confidence": 0.5}

        best_type = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_type] / 2)

        return {"type": best_type, "confidence": confidence}

    def _classify_experience_level(self, text: str) -> Dict[str, Any]:
        """Classify experience level from text."""
        text_lower = text.lower()
        scores = {}

        for level, patterns in self.EXPERIENCE_PATTERNS.items():
            score = sum(1 for pattern in patterns if re.search(pattern, text_lower))
            if score > 0:
                scores[level] = score

        if not scores:
            # Try to extract years of experience
            years_match = re.search(r"(\d+)[\s-]*(?:year|yr|y)", text_lower)
            if years_match:
                years = int(years_match.group(1))
                if years <= 1:
                    return {"level": "entry", "confidence": 0.7}
                elif years <= 3:
                    return {"level": "junior", "confidence": 0.7}
                elif years <= 5:
                    return {"level": "mid", "confidence": 0.7}
                else:
                    return {"level": "senior", "confidence": 0.7}
            return {"level": "entry", "confidence": 0.3}

        best_level = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_level] / 2)

        return {"level": best_level, "confidence": confidence}

    def _classify_security_domain(self, text: str) -> List[Dict[str, Any]]:
        """Classify security domains from text."""
        text_lower = text.lower()
        domains = []

        for domain, patterns in self.SECURITY_DOMAINS.items():
            matches = sum(1 for pattern in patterns if re.search(pattern, text_lower))
            if matches > 0:
                confidence = min(1.0, matches / 2)
                domains.append({"domain": domain, "confidence": confidence})

        # Sort by confidence
        domains.sort(key=lambda x: x["confidence"], reverse=True)
        return domains

    def _extract_skills(self, text: str) -> List[Dict[str, Any]]:
        """Extract and normalize skills from text."""
        text_lower = text.lower()
        found_skills = []

        for skill, patterns in self.SKILL_DATABASE.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    found_skills.append({"skill": skill, "category": self._get_skill_category(skill)})
                    break

        # Remove duplicates
        seen = set()
        unique_skills = []
        for skill in found_skills:
            if skill["skill"] not in seen:
                seen.add(skill["skill"])
                unique_skills.append(skill)

        return unique_skills

    def _get_skill_category(self, skill: str) -> str:
        """Get category for a skill."""
        programming = {"Python", "JavaScript", "Go", "Rust", "PowerShell", "Bash", "SQL"}
        cloud = {"AWS", "Azure", "GCP", "Kubernetes", "Docker"}
        security_tools = {"Nmap", "Burp Suite", "Wireshark", "Metasploit", "Nessus",
                         "Splunk", "SIEM", "Microsoft Sentinel", "Elastic"}
        concepts = {"OWASP", "MITRE ATT&CK", "Zero Trust", "Cryptography"}

        if skill in programming:
            return "programming"
        elif skill in cloud:
            return "cloud"
        elif skill in security_tools:
            return "security_tools"
        elif skill in concepts:
            return "concepts"
        return "other"

    async def process(
        self,
        job: Dict[str, Any],
        **kwargs,
    ) -> EngineResult:
        """
        Classify a job listing.

        Args:
            job: Job dictionary to classify

        Returns:
            EngineResult with classification data
        """
        # Combine all text fields
        text = " ".join([
            job.get("title", ""),
            job.get("description", ""),
            job.get("company_name", ""),
            " ".join(job.get("required_skills", [])),
        ])

        # Classify job type
        job_type = self._classify_job_type(text)

        # Classify experience level
        experience = self._classify_experience_level(text)

        # Classify security domains
        security_domains = self._classify_security_domain(text)

        # Extract skills
        skills = self._extract_skills(text)

        # Determine primary domain
        primary_domain = security_domains[0]["domain"] if security_domains else "General"

        return self._create_result(
            success=True,
            data={
                "job_type": job_type,
                "experience_level": experience,
                "security_domains": security_domains,
                "primary_domain": primary_domain,
                "skills": skills,
                "skills_list": [s["skill"] for s in skills],
                "skill_categories": list(set(s["category"] for s in skills)),
            },
            job_id=job.get("id"),
        )

    async def classify_batch(
        self,
        jobs: List[Dict[str, Any]],
    ) -> EngineResult:
        """Classify multiple jobs."""
        results = []

        for job in jobs:
            result = await self.process(job)
            if result.success:
                results.append({
                    "job_id": job.get("id"),
                    "classification": result.data,
                })

        # Aggregate statistics
        all_domains = []
        all_skills = []
        for r in results:
            all_domains.extend(r["classification"].get("security_domains", []))
            all_skills.extend(r["classification"].get("skills", []))

        # Count domain occurrences
        domain_counts = {}
        for d in all_domains:
            domain = d["domain"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Count skill occurrences
        skill_counts = {}
        for s in all_skills:
            skill = s["skill"]
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

        return self._create_result(
            success=True,
            data={
                "total_classified": len(results),
                "classifications": results,
                "domain_distribution": domain_counts,
                "skill_distribution": skill_counts,
                "top_domains": sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:5],
                "top_skills": sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            }
        )
