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
    "data_analysis": [
        "sql",
        "mysql",
        "postgresql",
        "excel",
        "advanced excel",
        "power bi",
        "tableau",
        "dax",
        "power query",
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "jupyter",
        "data analysis",
        "data analytics",
        "data visualization",
        "data cleaning",
        "data transformation",
        "etl",
        "statistics",
        "statistical analysis",
        "machine learning",
        "kpi dashboards",
        "dashboards",
        "reporting",
        "business intelligence",
    ],
}

# URL patterns
# NOTE: order matters — specific platform patterns are checked first, and the
# generic "portfolio" pattern must not capture bare domains of known platforms
# (e.g. "https://linkedin.com" when a profile URL was already extracted).
URL_PATTERNS = {
    "github": r"https?://(?:www\.)?github\.com/[\w-]+",
    "linkedin": r"https?://(?:www\.)?linkedin\.com/in/[\w-]+",
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

        # Fallback 2: pypdf (pure Python, installs everywhere incl. Vercel).
        # Handles CID/ToUnicode-mapped fonts and complex PDFs far better than
        # the regex fallback (e.g. Word/Google Docs exports whose glyphs the
        # raw-stream parser can't decode).
        try:
            import pypdf

            reader = pypdf.PdfReader(file_path)
            full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if full_text.strip():
                return full_text
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback 3: basic PDF text extraction (no external deps).
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
        # Normalize Symbol-font bullets (\uf0b7, produced by e.g. Word/Google
        # Docs PDF exports) to the standard bullet so section parsers that
        # rely on \u2022 keep working.
        text = text.replace("\uf0b7", "\u2022").replace("\ufffd", "\u2022")
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
            r"EDUCATION\s*\n(.*?)(?=\n(?:SKILLS?|EXPERIENCE|CERTIFICATIONS?|CERTIFICATES?|PROJECTS?|ACTIVITIES|HANDS|SUMMARY|CONTACT)|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        edu_text = edu_section_match.group(1) if edu_section_match else text

        # Degree detection within education section. Stop at a year range, a
        # CGPA marker, a newline, OR an institution keyword so a degree line
        # that wraps ("Bachelor of Engineering Computer Science Keystone School
        # of Engineering...") doesn't bleed the institution into the degree.
        degree_match = re.search(
            r"(b\.?tech|bachelor|b\.?e\.?|m\.?tech|master|mba|ph\.?d|diploma|b\.?sc|m\.?sc)"
            r"([^\n]{0,120}?)(?=\s*(?:20[12]\d|19\d{2})|\s*\\|\s*cgpa|\s*[|/]\s*cgpa|"
            r"\s+(?:[A-Z][a-z]+\s+)?(?:university|college|institute|academy|school)\b|\n|$)",
            edu_text,
            re.IGNORECASE,
        )
        if degree_match:
            degree = degree_match.group(0).strip() or None
        else:
            degree = None

        # Institution detection. The school keyword may appear AFTER the degree
        # ("...Computer Science Keystone School of Engineering, Pune") or
        # BEFORE it ("Mahendra Engineering College, Salem - B.Tech...").
        # Strategy: find the keyword, then (a) extend one preceding capitalized
        # proper-noun run as the school's name prefix — unless that run already
        # belongs to the degree (starts with a degree keyword) — and (b) take
        # everything after the keyword up to a dash / pipe / year / CGPA.
        institution = None
        degree_end = degree_match.end() if degree_match else -1
        for m in re.finditer(
            r"(university|college|institute|academy|school)\b", edu_text, re.IGNORECASE
        ):
            rest = edu_text[m.start() :]
            cut = re.search(r"\s*[–-]\s*|\s*\|\s*|\s*[|/]\s*cgpa|\s*(?:20[12]\d|19\d{2})", rest)
            if cut:
                rest = rest[: cut.start()]
            suffix = re.sub(r"\s+", " ", rest).strip().rstrip(",")
            if not suffix:
                continue

            before = edu_text[max(0, m.start() - 80) : m.start()]
            prefix = ""
            if m.start() < degree_end:
                # School keyword BEFORE the degree ("Mahendra Engineering
                # College, Salem - B.Tech..."): the whole preceding proper-noun
                # run is the school name.
                prefix_m = re.search(r"([A-Z][A-Za-z&.'-]*(?:\s+[A-Z][A-Za-z&.'-]*)*)\s*$", before)
                if prefix_m:
                    prefix = prefix_m.group(1)
            else:
                # School keyword AFTER the degree ("...Computer Science Keystone
                # School of Engineering"): only the one capitalized token
                # immediately before the keyword belongs to the school name.
                prefix_m = re.search(r"([A-Z][A-Za-z&.'-]*)\s*$", before)
                if prefix_m and len(prefix_m.group(1)) > 2:
                    prefix = prefix_m.group(1)

            candidate = f"{prefix} {suffix}".strip()
            if candidate:
                institution = candidate
                break

        # GPA/CGPA. Prefer a value with a scale suffix ("6.75/10"), then a
        # decimal GPA ("CGPA 7 th sem : 8.65" → 8.65, not 7), then the last
        # plain number. Only look on the degree line so HSC/SSC percentages
        # stay out.
        degree_line = ""
        if degree:
            d_idx = edu_text.find(degree)
            if d_idx != -1:
                degree_line = edu_text[d_idx : d_idx + 200]
        gpa = None
        gpa_region = degree_line or edu_text
        for m in re.finditer(r"(?:cgpa|gpa|percentage|grades?)\b[^\n]*", gpa_region, re.IGNORECASE):
            candidates = re.findall(r"\d+(?:\.\d+)?(?:/\d+)?", m.group(0))
            if not candidates:
                continue
            scaled = [c for c in candidates if "/" in c]
            decimal = [c for c in candidates if "." in c and "/" not in c]
            gpa = (scaled or decimal or [candidates[-1]])[-1]
            break

        # Year range - prefer the degree entry itself (so HSC/SSC ranges on
        # later bullet lines don't win). The degree region may wrap across
        # lines ("...School of \nEngineering, Pune - 2026") but ends at the
        # next bullet; search only up to the next bullet. Accept a single
        # year when no range is present.
        years = None
        degree_entry = degree_line.split("\u2022", 1)[0] if degree_line else ""
        degree_entry = degree_entry or degree_line or edu_text
        year_match = re.search(
            r"(20[12]\d)\s*[-–]\s*(20[12]\d|present)", degree_entry, re.IGNORECASE
        )
        if year_match:
            years = f"{year_match.group(1)} - {year_match.group(2)}"
        else:
            single = re.search(r"(?:20[12]\d|19\d{2})", degree_entry)
            if single:
                years = single.group(0)
            elif degree_line:
                fallback = re.search(
                    r"(20[12]\d)\s*[-–]\s*(20[12]\d|present)", edu_text, re.IGNORECASE
                )
                if fallback:
                    years = f"{fallback.group(1)} - {fallback.group(2)}"

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
        """Extract certifications.

        Two passes: (1) known security-cert keywords (word-boundary matched),
        (2) generic "Certificate of X" / "Certified X" lines (e.g. "Certificate
        of Advanced Excel") so non-security resumes are also covered.
        """
        certs = []
        seen = set()
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
                name = cert.upper() if len(cert) <= 5 else cert.title()
                if name not in seen:
                    seen.add(name)
                    certs.append(
                        {
                            "name": name,
                            "status": "in progress"
                            if "progress" in context.lower()
                            else "completed",
                            "context": context.strip(),
                        }
                    )

        # Generic "Certificate of X" / "Certified in X" lines.
        for m in re.finditer(
            r"certificate\s+of\s+([A-Za-z][\w &+.-]{2,60}?)(?=\s*(?:–|-|,|\n|$))",
            text,
            re.IGNORECASE,
        ):
            name = m.group(1).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            line_start = text.rfind("\n", 0, m.start()) + 1
            context = text[line_start : m.start() + len(name) + 60].strip()
            certs.append(
                {
                    "name": name.title(),
                    "status": "in progress" if "progress" in context.lower() else "completed",
                    "context": context,
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
        projects: list[dict[str, Any]] = []
        seen_names = set()

        # Normalize Symbol-font bullets here too (direct calls to this method
        # skip _parse_text's normalization).
        text = text.replace("\uf0b7", "\u2022").replace("\ufffd", "\u2022")

        # Match only a PROJECTS header (explicitly, not labs / hands-on).
        # MULTILINE so ^ matches the line start mid-string; \Z is the absolute
        # end so the lookahead doesn't stop at every line break.
        project_section = re.search(
            r"^\s*PROJECTS?\s*\n(.*?)(?=\n(?:certifications?|certificates?|education|skills?|experience|activities?|additional|key competencies|awards?|contact)|\Z)",
            text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )

        if project_section:
            section_text = project_section.group(1)

            # Bullet characters — include U+FFFD (the replacement char produced
            # when PDF extraction loses the original "•" glyph).
            date_re = re.compile(
                r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4}$",
                re.IGNORECASE,
            )

            lines = [raw_line.strip() for raw_line in section_text.split("\n")]
            lines = [ln for ln in lines if ln]

            # Determine layout from the bullet combination:
            #   dot + dash → "\u2022 Title" + "- detail" (Pizza Dashboard style)
            #   dot only + plain → plain title lines + "\u2022 detail" (real
            #       resume style)
            #   dot only → each dot is its own project
            #   dash only → each dash is its own project
            #   no bullets → title/detail heuristic
            # Non-bullet lines that follow a bullet without sentence-ending
            # punctuation are wrapped continuations and attach as details.
            dot_bullet_re = re.compile(r"^\s*[\u2022\ufffd]+\s*")
            dash_bullet_re = re.compile(r"^\s*-\s*")

            def _is_metadata(ln: str) -> bool:
                return bool(
                    ln.lower().startswith("report:")
                    or re.match(r"^https?://", ln)
                    or date_re.match(ln)
                )

            entries: list[list[str]] = []  # each entry: [title, ...details]
            has_dot = any(dot_bullet_re.match(ln) for ln in lines)
            has_dash = any(dash_bullet_re.match(ln) for ln in lines)
            has_plain = any(
                not dot_bullet_re.match(ln) and not dash_bullet_re.match(ln) for ln in lines
            )

            def _strip_dash(ln: str) -> str:
                return re.sub(r"^\s*-\s*", "", ln).strip()

            def _strip_dot(ln: str) -> str:
                return dot_bullet_re.sub("", ln).strip()

            current: list[str] | None = None

            def _start(clean: str) -> None:
                nonlocal current
                if current is not None:
                    entries.append(current)
                current = [clean] if clean else None

            def _detail(clean: str) -> None:
                if current is not None and clean:
                    current.append(clean)

            if has_dot and has_dash:
                # "\u2022 Title" starts a project; "- detail" and wrapped
                # continuation lines attach to it.
                for ln in lines:
                    if _is_metadata(ln):
                        continue
                    if dot_bullet_re.match(ln):
                        _start(_strip_dot(ln))
                    elif dash_bullet_re.match(ln):
                        _detail(_strip_dash(ln))
                    else:
                        _detail(ln.strip())
            elif (has_dot or has_dash) and has_plain:
                # Plain lines are titles; bullets (dot or dash) are details;
                # wrapped continuations attach.
                for ln in lines:
                    if _is_metadata(ln):
                        continue
                    if dot_bullet_re.match(ln):
                        _detail(_strip_dot(ln))
                    elif dash_bullet_re.match(ln):
                        _detail(_strip_dash(ln))
                    else:
                        _start(ln.strip())
            elif has_dot:
                # Plain dot bullet list: each bullet is its own project.
                for ln in lines:
                    if _is_metadata(ln):
                        continue
                    clean = _strip_dot(ln)
                    if clean:
                        entries.append([clean])
            elif has_dash:
                # Plain dash bullet list: each bullet is its own project.
                for ln in lines:
                    if _is_metadata(ln):
                        continue
                    clean = _strip_dash(ln)
                    if clean:
                        entries.append([clean])
            else:
                # No bullets (common in PDFs): a project title typically has a
                # dash separator ("Title - Detail"), or a year in parentheses,
                # or is a short line without commas/sentence punctuation.
                for ln in lines:
                    if _is_metadata(ln):
                        continue
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

            if current is not None and current not in entries:
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
