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
# NOTE: order matters — specific platform patterns are checked first, and the
# generic "portfolio" pattern must not capture bare domains of known platforms
# (e.g. "https://linkedin.com" when a profile URL was already extracted).
URL_PATTERNS = {
    "github": r"https?://github\.com/[\w-]+",
    "linkedin": r"https?://linkedin\.com/in/[\w-]+",
    "tryhackme": r"https?://tryhackme\.com/p/[\w-]+",
    "hackthebox": r"https?://app\.hackthebox\.me/users/[\w-]+",
    # Custom portfolio domains only — exclude the dedicated platforms above
    # (and other common link platforms) so we never report a bare platform URL.
    "portfolio": r"https?://(?![\.\w-]*\.?(?:linkedin|github|tryhackme|hackthebox|mediafire|facebook|twitter|instagram|youtube|whatsapp)\.(?:com|me|org|net|io))[\w-]+\.(?:dev|io|com|net|org)(?:/[\w./-]*)?",
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

            # Extract text from PDF text-showing operators. Real-world PDFs
            # (e.g. LibreOffice/Canva exports) split words into kerning arrays:
            #   [(P)100(AR)20(THASARA)90(THI)-278(B)]TJ
            # so all (..) fragments inside one array must be joined, inserting a
            # space when a large negative kerning value (a word gap) separates
            # fragments. Also handle single (text) Tj and hex strings <...> Tj.
            # All patterns are simple/bounded to avoid catastrophic backtracking.
            pieces = []

            # 1) TJ arrays: [(frag)num(frag)...] TJ — join fragments, inserting
            #    spaces at word gaps (large negative kerning numbers).
            for m in re.finditer(r"\[(.*?)\]\s*TJ", stream_content):
                joined = self._join_tj_fragments(m.group(1))
                if joined:
                    pieces.append(joined)

            # 2) Plain single-string operators: (text) Tj / ' / "
            for t in re.findall(r"\(([^)]*)\)\s*(?:Tj|'|\")", stream_content):
                pieces.append(t)

            # 3) Hex strings <...> Tj (common with embedded CID fonts) — only
            # used when no literal-string text was found above.
            if not pieces:
                for m in re.finditer(r"<([0-9A-Fa-f]+)>\s*Tj", stream_content):
                    hexstr = m.group(1)
                    try:
                        pieces.append(bytes.fromhex(hexstr).decode("latin-1", errors="replace"))
                    except ValueError:
                        pass

            for piece in pieces:
                clean = self._clean_pdf_text(piece)
                if len(clean) > 1:
                    text_parts.append(clean)

        return "\n".join(text_parts)

    @staticmethod
    def _clean_pdf_text(piece: str) -> str:
        """Normalize a PDF text fragment to printable ASCII.

        PDFs (esp. LibreOffice exports) use CP1252 control chars for smart
        punctuation: chr(0x95) is bullet \u2022, smart quotes are 0x91-0x94,
        dashes 0x96/0x97. Map those to ASCII so downstream section parsers
        (which rely on \u2022 bullets) keep working.
        """
        out = []
        for c in piece:
            o = ord(c)
            if 32 <= o < 127 or c in " \n\r":
                out.append(c)
            elif o == 0x95:
                out.append("\u2022")  # bullet
            elif o in (0x91, 0x92):
                out.append("'")
            elif o in (0x93, 0x94):
                out.append('"')
            elif o in (0x96, 0x97):
                out.append("-")
            elif c == "\u2019":
                out.append("'")
            elif c == "\u201c":
                out.append('"')
            elif c == "\u201d":
                out.append('"')
            elif c == "\u2013":
                out.append("-")
            elif c == "\u2014":
                out.append("-")
            # other control chars dropped
        return "".join(out)

    @staticmethod
    def _join_tj_fragments(array_body: str) -> str:
        """Join the (..) fragments of a TJ array body into a text string.

        A large negative kerning number between fragments marks a word gap
        (PDFs encode spaces this way instead of literal space chars). PDF
        escape sequences inside strings (\\(, \\), \\\\, octal \\ddd) are
        unescaped. Returns "" when the body contains no string fragments.
        """
        parts: list[str] = []
        for frag in re.finditer(r"\(([^)]*)\)\s*(-?\d+(?:\.\d+)?)?", array_body):
            raw = frag.group(1)
            kerning = frag.group(2)
            # Unescape PDF string escapes.
            raw = re.sub(r"\\([()\\])", r"\1", raw)
            raw = re.sub(r"\\([0-7]{1,3})", lambda mm: chr(int(mm.group(1), 8)), raw)
            parts.append(raw)
            # Large negative kerning (~ <-150) indicates a word gap.
            if kerning and float(kerning) < -150:
                parts.append(" ")
        return "".join(parts)

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
        """Extract skills by matching against the cybersecurity skill database.

        Uses word boundaries so short keywords ("go", "dd", "ids") only match
        as standalone words and never inside unrelated words (e.g. "Google",
        "Conducted", "Identification").
        """
        found = []
        seen = set()

        for keyword, category in self._all_skills.items():
            # Multi-word keywords still get boundaries on both ends.
            pattern = r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(keyword))
            if keyword not in seen and re.search(pattern, text_lower):
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

        # Degree detection within education section - stop at newline, a year
        # range, or a CGPA marker so "B.Tech in IT 2021-2025 / CGPA" on a
        # single line (common in extracted PDFs) doesn't bleed together.
        degree_match = re.search(
            r"(b\.?tech|bachelor|b\.?e\.?|m\.?tech|master|mba|ph\.?d|diploma|b\.?sc|m\.?sc)([^\n]{0,120}?)(?=\s*(?:20[12]\d|19\d{2})|\s*\\|\s*cgpa|\s*[|/]\s*cgpa|\n|$)",
            edu_text,
            re.IGNORECASE,
        )
        if degree_match:
            degree = (degree_match.group(0).strip()) or None
        else:
            degree = None

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
        """Extract work experience information.

        Only matches role keywords as standalone words (word boundaries) on
        lines that actually look like job titles — the keyword appears at the
        start of the line, or the line contains " at <company>" or a date
        range. This avoids false positives from prose such as "SOC Analyst
        Training", "Engineering College", "Team leadership".
        """
        experience = []
        seen_roles = set()

        # Role keywords, matched as standalone words only.
        role_keywords = [
            "intern",
            "internship",
            "trainee",
            "junior",
            "senior",
            "lead",
            "analyst",
            "engineer",
            "associate",
        ]

        for line in text.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            line_lower = line_stripped.lower()

            for role in role_keywords:
                role_pattern = r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(role))
                if not re.search(role_pattern, line_lower):
                    continue

                # Skip lines that are section headers or clearly not titles.
                if re.search(r"(skills?|education|certifications?|projects?|summary)", line_lower):
                    continue

                # Skip "<role> Training" patterns — course names, not roles
                # (e.g. "SOC Analyst Training").
                if re.search(r"{}\s+training\b".format(role), line_lower):
                    continue

                # A line is a plausible job title when the role is at the
                # start (after bullets/whitespace) OR the line mentions a
                # company (" at ") OR contains a date range.
                role_at_start = re.match(r"^[\s\-•*]*{}".format(role), line_lower) is not None
                has_company = r" at " in line_lower or r" - " in line_lower
                has_date = re.search(r"\b(19|20)\d{2}\b", line_lower) is not None

                if not (role_at_start or has_company or has_date):
                    continue

                # Skip education/institution context (e.g. "Engineering" is
                # already excluded by word boundaries, but guard anyway).
                if re.search(r"(college|university|academy|school)", line_lower):
                    continue

                if role not in seen_roles:
                    seen_roles.add(role)
                    experience.append(
                        {
                            "role": role,
                            "context": line_stripped[:200],
                        }
                    )

        return experience

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
            # Word-boundary match so "comp security+" doesn't hit "CompTIA",
            # and standalone "ceh"/"oscp" aren't matched inside other words.
            pattern = r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(cert))
            match = re.search(pattern, text_lower)
            if match:
                idx = match.start()
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
        """Extract project information.

        Only the PROJECTS section is considered (NOT "hands-on labs", "key
        competencies", etc. — those are lists of skills/activities, not
        projects). Bullet items and URL/report lines inside the section are
        skipped so each entry is a real project.
        """
        projects = []
        seen_names = set()

        # Match only a PROJECTS header (explicitly, not labs / hands-on).
        # MULTILINE so ^ matches the line start mid-string; \Z is the absolute
        # end so the lookahead doesn't stop at every line break.
        project_section = re.search(
            r"^\s*PROJECTS?\s*\n(.*?)(?=\n(?:certifications?|education|skills?|experience|activities?|additional|key competencies|awards?|contact)|\Z)",
            text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )

        if project_section:
            section_text = project_section.group(1)

            # Bullet characters — include U+FFFD (the replacement char produced
            # when PDF extraction loses the original "•" glyph).
            bullet_re = re.compile(r"^[\s\-•*\u2022\ufffd]+\s*")
            date_re = re.compile(
                r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4}$",
                re.IGNORECASE,
            )

            lines = [raw_line.strip() for raw_line in section_text.split("\n")]
            lines = [ln for ln in lines if ln]

            # Determine layout: if every non-empty line is a bullet, treat each
            # bullet as its own project (classic list style). Otherwise, bullets
            # are details under the preceding title line (resume style).
            non_bullet_lines = [ln for ln in lines if not bullet_re.match(ln)]
            all_bullets = len(non_bullet_lines) == 0

            # Lines that are clearly NOT project titles.
            def _is_metadata(ln: str) -> bool:
                return (
                    ln.lower().startswith("report:")
                    or re.match(r"^https?://", ln)
                    or bool(date_re.match(ln))
                )

            entries: list[list[str]] = []  # each entry: [title, ...details]
            if all_bullets:
                for ln in lines:
                    clean = bullet_re.sub("", ln).strip()
                    if clean:
                        entries.append([clean])
            else:
                has_any_bullet = any(bullet_re.match(ln) for ln in lines)
                current: list[str] | None = None
                for ln in lines:
                    if _is_metadata(ln):
                        continue
                    is_bullet = bullet_re.match(ln)
                    if has_any_bullet:
                        # Explicit bullets: details attach to current project.
                        if is_bullet:
                            clean = bullet_re.sub("", ln).strip()
                            if current is None:
                                current = [clean]
                            else:
                                current.append(clean)
                        else:
                            if current is not None:
                                entries.append(current)
                            current = [ln]
                    else:
                        # No bullets (common in PDFs): a project title typically
                        # has a dash separator ("Title - Detail"), or a year in
                        # parentheses, or is a short line without commas/sentence
                        # punctuation. Detail lines are longer and comma-heavy.
                        looks_like_title = (
                            re.search(r"\s[-\u2013\u2014]\s", ln) is not None
                            or re.search(r"\((?:19|20)\d{2}", ln) is not None
                            or (
                                len(ln) <= 50
                                and "," not in ln
                                and not ln.rstrip().endswith((".", ":", ";"))
                                and re.search(r"[A-Za-z]", ln) is not None
                            )
                        )
                        if current is None or looks_like_title:
                            if current is not None and looks_like_title:
                                entries.append(current)
                            current = [ln]
                        else:
                            current.append(ln)
                if current is not None:
                    entries.append(current)

            output = []
            for entry in entries:
                title = entry[0].strip()
                title_key = title.lower()[:60]
                if len(title) <= 2 or title_key in seen_names:
                    continue
                seen_names.add(title_key)
                description = (title + "\n" + "\n".join(entry[1:])).strip()[:500]

                # Extract technologies mentioned.
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
                    if tech in description.lower():
                        techs.append(tech.title())

                output.append(
                    {
                        "name": title[:100],
                        "description": description,
                        "technologies": techs,
                    }
                )
            return output

        return projects

    def _extract_links(self, text: str) -> Dict[str, str]:
        """Extract social/professional links."""
        links = {}

        for link_type, pattern in URL_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                links[link_type] = match.group(0).strip()

        return links
