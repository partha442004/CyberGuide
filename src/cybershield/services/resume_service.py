"""
Resume Parsing Service

Extracts structured data from PDF/DOCX resume files:
- Skills (matched against cybersecurity skill database)
- Education (degree, institution, GPA, year)
- Experience (company, role, duration)
- Certifications (name, provider, status)
- Projects (name, description, technologies)
- Social links (GitHub, LinkedIn, TryHackMe, etc.)
"""

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Comprehensive cybersecurity skill keywords
SECURITY_SKILLS = {
    "vulnerability_assessment": [
        "nessus",
        "openvas",
        "qualys",
        "nexpose",
        "retina",
        "cvss",
        "risk rating",
        "vulnerability scan",
        "vulnerability assessment",
        "cve",
        "cwe",
        "vulnerability management",
    ],
    "penetration_testing": [
        "penetration testing",
        "pentest",
        "ethical hacking",
        "exploitation",
        "metasploit",
        "burp suite",
        "owasp zap",
        "sqlmap",
        "nikto",
        "web application testing",
        "network pentesting",
        "owasp top 10",
        "web app testing",
        "vapt",
        "red team",
        "blue team",
    ],
    "security_tools": [
        "nmap",
        "wireshark",
        "kali linux",
        "hydra",
        "john the ripper",
        "hashcat",
        "aircrack-ng",
        "burp suite",
        "owasp zap",
        "metasploit",
        "gobuster",
        "dirb",
        "subfinder",
        "httpx",
        "sqlmap",
        "wpscan",
        "ffuf",
        "amass",
        "theHarvester",
    ],
    "reconnaissance": [
        "recon",
        "passive recon",
        "active recon",
        "osint",
        "google dorks",
        "shodan",
        "censys",
        "maltego",
        "recon-ng",
        "subdomain enumeration",
    ],
    "privilege_escalation": [
        "privilege escalation",
        "privesc",
        "suid",
        "sudo abuse",
        "kernel exploit",
        "linux privesc",
        "windows privesc",
        "linpeas",
        "winpeas",
    ],
    "forensics": [
        "digital forensics",
        "incident response",
        "malware analysis",
        "volatility",
        "autopsy",
        "ftk",
        "en_case",
        "dd",
        "foremost",
        "reverse engineering",
        "ida pro",
        "ghidra",
        "binary analysis",
    ],
    "cloud_security": [
        "aws security",
        "azure security",
        "gcp security",
        "cloud security",
        "iam",
        "identity and access management",
        "s3",
        "ec2",
        "lambda",
        "cloudtrail",
        "guardduty",
        "security hub",
    ],
    "siem": [
        "siem",
        "splunk",
        "microsoft sentinel",
        "elastic security",
        "qradar",
        "wazuh",
        "log analysis",
        "log analytics",
        "kql",
        "splunk query",
    ],
    "network_security": [
        "firewall",
        "ids",
        "ips",
        "vpn",
        "network security",
        "tcpdump",
        "netflow",
        "packet analysis",
        "tcp/ip",
        "dns",
        "dhcp",
        "proxy",
    ],
    "web_security": [
        "xss",
        "csrf",
        "sql injection",
        "ssrf",
        "xxe",
        "idor",
        "authentication bypass",
        "session management",
        "cors",
        "csp",
        "jwt",
        "oauth",
        "saml",
        "portswigger",
        "juice shop",
        "dvwa",
        "hackthebox",
        "tryhackme",
    ],
    "scripting": [
        "python",
        "bash",
        "powershell",
        "javascript",
        "go",
        "rust",
        "automation",
        "scripting",
        "bash scripting",
    ],
    "compliance": [
        "gdpr",
        "hipaa",
        "pci dss",
        "iso 27001",
        "soc 2",
        "grc",
        "compliance",
        "risk management",
        "policy",
        "audit",
        "nist",
        "cis",
    ],
    "certifications": [
        "ceh",
        "comptia security+",
        "cissp",
        "oscp",
        "oswe",
        "osep",
        "pnpt",
        "ejpt",
        "crtp",
        "crto",
        "gsec",
        "gpen",
        "security+ certification",
        "advanced pentester",
    ],
    "cicd_security": [
        "devsecops",
        "cicd security",
        "container security",
        "kubernetes security",
        "docker security",
        "sonarqube",
        "snyk",
        "trivy",
        "fortify",
    ],
}

# URL patterns
URL_PATTERNS = {
    "github": r"https?://github\.com/[\w-]+",
    "linkedin": r"https?://linkedin\.com/in/[\w-]+",
    "tryhackme": r"https?://tryhackme\.com/p/[\w-]+",
    "hackthebox": r"https?://app\.hackthebox\.me/users/[\w-]+",
    "portfolio": r"https?://[\w-]+\.(dev|io|com|net|org)",
    "email": r"[\w.-]+@[\w.-]+\.\w+",
    "phone": r"\+?\d[\d\s-]{8,13}",
}


class ResumeParser:
    """Parse resume PDFs and extract structured data."""

    def __init__(self):
        self._all_skills = self._flatten_skills()

    def _flatten_skills(self) -> Dict[str, str]:
        """Flatten skill categories into a keyword→category mapping."""
        mapping = {}
        for category, skills in SECURITY_SKILLS.items():
            for skill in skills:
                mapping[skill.lower()] = category
        return mapping

    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from a PDF using available libraries.

        Tries pymupdf (fast, best quality) first, then falls back to a
        basic PDF text extraction that works without native dependencies.
        """
        try:
            import pymupdf

            doc = pymupdf.open(file_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()
            return full_text
        except ImportError:
            pass

        # Fallback: basic PDF text extraction (no native deps).
        # Handles common PDF encodings with pure stdlib:
        #   - ASCII85 (+ FlateDecode) streams (e.g. reportlab output)
        #   - Plain FlateDecode (zlib) streams
        #   - Raw/uncompressed streams
        # Then extracts text from PDF operators (Tj, TJ, ', ").
        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception:
            return ""

        import base64
        import zlib

        text_parts: list[str] = []
        content = data.decode("latin-1", errors="replace")

        # Find stream sections. Do NOT require whitespace before "endstream":
        # binary payloads frequently end flush against the keyword (e.g.
        # ASCII85 "~>endstream" or raw bytes ending in ">endstream").
        for m in re.finditer(r"stream\r?\n(.*?)endstream", content, re.DOTALL):
            raw = m.group(1).strip()
            if not raw:
                continue
            raw_bytes = raw.encode("latin-1")
            stream_content = None

            # 1) ASCII85 (Base85) encoded streams
            if raw_bytes[:1].isalpha() or b"~>" in raw_bytes or b"~" in raw_bytes[-2:]:
                a85_bytes = raw_bytes
                # Strip the ASCII85 end-of-data marker if present.
                for suffix in (b"~>", b"~"):
                    if a85_bytes.endswith(suffix):
                        a85_bytes = a85_bytes[: -len(suffix)]
                        break
                try:
                    decoded = base64.a85decode(a85_bytes)
                    try:
                        stream_content = zlib.decompress(decoded).decode(
                            "latin-1", errors="replace"
                        )
                    except Exception:
                        try:
                            stream_content = zlib.decompress(decoded, -15).decode(
                                "latin-1", errors="replace"
                            )
                        except Exception:
                            stream_content = decoded.decode("latin-1", errors="replace")
                except Exception:
                    pass

            # 2) FlateDecode (zlib) streams
            if stream_content is None:
                try:
                    decompressed = zlib.decompress(raw_bytes)
                    stream_content = decompressed.decode("latin-1", errors="replace")
                except Exception:
                    try:
                        decompressed = zlib.decompress(raw_bytes, -15)
                        stream_content = decompressed.decode("latin-1", errors="replace")
                    except Exception:
                        stream_content = raw

            # Extract text from PDF operators: (text) Tj, (text) ', (text) "
            texts = re.findall(r"\(([^)]*)\)\s*(?:Tj|'|\"|TJ)", stream_content)
            for t in texts:
                clean = "".join(c for c in t if 32 <= ord(c) < 127 or c in " \n\r")
                if len(clean) > 1:
                    text_parts.append(clean)

            # Also try parenthesized text not followed by an operator
            texts = re.findall(r"\(([^)]*)\)", stream_content)
            for t in texts:
                clean = "".join(c for c in t if 32 <= ord(c) < 127 or c in " \n\r")
                if len(clean) > 3 and clean not in text_parts:
                    text_parts.append(clean)

        return "\n".join(text_parts)

    async def parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """Parse a PDF resume and extract structured data."""
        full_text = self._extract_pdf_text(file_path)
        return self._parse_text(full_text, file_path)

    async def parse_upload(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse uploaded file content (PDF) and extract structured data."""
        import tempfile

        # Save to temp file
        suffix = os.path.splitext(filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            if suffix == ".pdf":
                result = await self.parse_pdf(tmp_path)
            else:
                # For now, only PDF is supported
                raise ValueError(f"Unsupported file format: {suffix}. Only PDF is supported.")

            result["file_hash"] = hashlib.sha256(file_content).hexdigest()
            result["file_name"] = filename
            return result
        finally:
            os.unlink(tmp_path)

    def _parse_text(self, text: str, file_path: str = "") -> Dict[str, Any]:
        """Parse extracted text and return structured resume data."""
        text_lower = text.lower()

        return {
            "skills": self._extract_skills(text_lower),
            "education": self._extract_education(text),
            "experience": self._extract_experience(text),
            "certifications": self._extract_certifications(text),
            "projects": self._extract_projects(text),
            "links": self._extract_links(text),
            "raw_text": text,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_skills(self, text_lower: str) -> List[Dict[str, Any]]:
        """Extract skills by matching against the cybersecurity skill database."""
        found = []
        seen = set()

        for keyword, category in self._all_skills.items():
            if keyword in text_lower and keyword not in seen:
                seen.add(keyword)
                found.append(
                    {
                        "name": keyword.title(),
                        "category": category,
                        "confidence": 0.9,
                    }
                )

        return found

    def _extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Extract education information by first isolating the Education section."""
        education = []

        # Isolate the Education section (between EDUCATION header and next section)
        edu_section_match = re.search(
            r"EDUCATION\s*\n(.*?)(?=\n(?:SKILLS?|EXPERIENCE|CERTIFICATIONS?|PROJECTS?|ACTIVITIES|HANDS|SUMMARY|CONTACT)|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        edu_text = edu_section_match.group(1) if edu_section_match else text

        # Degree detection within education section - stop at newline
        degree_match = re.search(
            r"(b\.?tech|bachelor|b\.?e\.?|m\.?tech|master|mba|ph\.?d|diploma|b\.?sc|m\.?sc)[\s,]*([^\n]+)",
            edu_text,
            re.IGNORECASE,
        )
        degree = degree_match.group(0).strip() if degree_match else None

        # Institution detection within education section - line-by-line, stop at dash
        institution = None
        for line in edu_text.split("\n"):
            line = line.strip()
            if re.search(r"(university|college|institute|academy|school)", line, re.IGNORECASE):
                # Split on dash and take first part
                parts = re.split(r"\s*[–-]\s*", line)
                institution = parts[0].strip()
                break

        # GPA/CGPA
        gpa_match = re.search(
            r"(cgpa|gpa|percentage|grades?)[\s:]*(\d+\.?\d*(?:/\d+)?)", edu_text, re.IGNORECASE
        )
        gpa = gpa_match.group(2) if gpa_match else None

        # Year range - search within education section for B.Tech context
        years = None
        year_match = re.search(r"(20[12]\d)\s*[-–]\s*(20[12]\d|present)", edu_text, re.IGNORECASE)
        if year_match:
            years = f"{year_match.group(1)} - {year_match.group(2)}"

        if degree or institution:
            education.append(
                {
                    "degree": degree,
                    "institution": institution,
                    "gpa": gpa,
                    "years": years,
                }
            )

        return education

    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """Extract work experience information."""
        experience = []

        # Intern/role detection
        role_patterns = [
            r"(intern|internship|trainee|junior|senior|lead|analyst|engineer|associate|cadet)",
        ]

        for pattern in role_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                context = text[max(0, match.start() - 100) : match.end() + 100]
                experience.append(
                    {
                        "role": match.group(0).strip(),
                        "context": context.strip()[:200],
                    }
                )

        # Deduplicate by role
        seen_roles = set()
        unique_exp = []
        for exp in experience:
            role_key = exp["role"].lower()
            if role_key not in seen_roles:
                seen_roles.add(role_key)
                unique_exp.append(exp)

        return unique_exp

    def _extract_certifications(self, text: str) -> List[Dict[str, Any]]:
        """Extract certifications."""
        certs = []
        cert_keywords = [
            "ceh",
            "comp security+",
            "cissp",
            "oscp",
            "oswe",
            "osep",
            "pnpt",
            "ejpt",
            "crtp",
            "crto",
            "gsec",
            "gpen",
            "security+",
            "advanced pentester",
            "certified",
        ]

        text_lower = text.lower()
        for cert in cert_keywords:
            if cert in text_lower:
                # Find context around the certification
                idx = text_lower.find(cert)
                context = text[max(0, idx - 50) : idx + len(cert) + 50]
                certs.append(
                    {
                        "name": cert.upper() if len(cert) <= 5 else cert.title(),
                        "status": "in progress" if "progress" in context.lower() else "completed",
                        "context": context.strip(),
                    }
                )

        return certs

    def _extract_projects(self, text: str) -> List[Dict[str, Any]]:
        """Extract project information."""
        projects = []

        # Look for project sections
        project_section = re.search(
            r"(projects?|labs?|hands[- ]?on)[\s:]*\n(.*?)(?=\n(?:certifications?|education|skills?|experience|activities?)|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if project_section:
            section_text = project_section.group(2)
            # Split by common separators
            items = re.split(r"\n\s*[-•*]\s*|\n\s*\d+\.\s*", section_text)

            for item in items:
                item = item.strip()
                if len(item) > 10:  # Skip very short items
                    # Extract title (first line or first sentence)
                    title_match = re.match(r"^([^\n.]+)", item)
                    title = title_match.group(1).strip() if title_match else item[:50]

                    # Extract technologies mentioned
                    techs = []
                    tech_keywords = [
                        "nessus",
                        "nmap",
                        "metasploit",
                        "burp",
                        "wireshark",
                        "owasp",
                        "dvwa",
                        "portswigger",
                        "hackthebox",
                        "tryhackme",
                    ]
                    for tech in tech_keywords:
                        if tech in item.lower():
                            techs.append(tech.title())

                    projects.append(
                        {
                            "name": title[:100],
                            "description": item[:500],
                            "technologies": techs,
                        }
                    )

        return projects

    def _extract_links(self, text: str) -> Dict[str, str]:
        """Extract social/professional links."""
        links = {}

        for link_type, pattern in URL_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                links[link_type] = match.group(0).strip()

        return links
