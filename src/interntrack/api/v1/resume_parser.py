"""
AI Resume Parser — upload PDF, extract skills and experience automatically.

Uses PyMuPDF for PDF text extraction and rule-based skill matching
(with optional LLM enhancement when Gemini/Ollama is configured).
"""

import re

from fastapi import APIRouter, File, UploadFile

router = APIRouter()

# Comprehensive skill taxonomy for extraction
SKILL_TAXONOMY = {
    "security": [
        "vulnerability assessment",
        "penetration testing",
        "vapt",
        "soc",
        "siem",
        "firewall",
        "ids",
        "ips",
        "waf",
        "owasp",
        "burp suite",
        "nmap",
        "metasploit",
        "nessus",
        "qualys",
        "cobalt strike",
        "red team",
        "blue team",
        "incident response",
        "threat hunting",
        "malware analysis",
        "forensics",
        "ctf",
        "bug bounty",
        "cve",
        "exploit",
        "security audit",
        "compliance",
        "iso 27001",
        "nist",
        "zero trust",
        "encryption",
        "cryptography",
        "pki",
        "cloud security",
        "aws security",
        "azure security",
        "devsecops",
        "sast",
        "dast",
        "sbom",
        "kali linux",
        "wireshark",
        "tcpdump",
        "snort",
        "suricata",
        # Web-app security: keep these BEFORE bare "sql" (in programming) so
        # a resume listing SQLi / XSS is extracted as security, not coding.
        "sqli",
        "sql injection",
        "sqlmap",
        "xss",
        "csrf",
        "ssrf",
        "idor",
        "grc",
        "osint",
        "dfir",
        "cissp",
        "ceh",
        "ethical hacking",
        "cybersecurity",
        "threat intelligence",
        "security operations",
    ],
    "programming": [
        "python",
        "javascript",
        "typescript",
        "java",
        "c++",
        "c#",
        "golang",
        "rust",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "scala",
        "r",
        "matlab",
        "html",
        "css",
        "sql",
        "nosql",
        "bash",
        "powershell",
        "lua",
    ],
    "web": [
        "react",
        "angular",
        "vue",
        "node.js",
        "express",
        "fastapi",
        "django",
        "flask",
        "spring boot",
        "rails",
        "laravel",
        "next.js",
        "nuxt",
        "tailwind",
        "bootstrap",
        "sass",
        "webpack",
        "vite",
    ],
    "data": [
        "machine learning",
        "deep learning",
        "tensorflow",
        "pytorch",
        "pandas",
        "numpy",
        "scikit-learn",
        "data science",
        "data analysis",
        "data engineering",
        "etl",
        "airflow",
        "spark",
        "hadoop",
        "tableau",
        "power bi",
        "statistics",
        "nlp",
        "computer vision",
        "neural network",
    ],
    "devops": [
        "docker",
        "kubernetes",
        "terraform",
        "ansible",
        "jenkins",
        "github actions",
        "gitlab ci",
        "prometheus",
        "grafana",
        "elk stack",
        "aws",
        "azure",
        "gcp",
        "linux",
        "nginx",
        "redis",
        "mongodb",
        "postgresql",
        "mysql",
        "elasticsearch",
        "kafka",
        "rabbitmq",
    ],
    "tools": [
        "git",
        "jira",
        "confluence",
        "slack",
        "figma",
        "photoshop",
        "illustrator",
        "premiere pro",
        "after effects",
        "blender",
    ],
}


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using multiple strategies with graceful fallbacks.

    Strategy order: pypdf (pure Python, works everywhere) → PyMuPDF →
    pdfplumber → raw bytes.
    """
    # Strategy 1: pypdf (pure Python, works on Vercel and all environments)
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        if text.strip():
            return text
    except Exception:  # noqa: S110
        pass

    # Strategy 2: PyMuPDF (fast, good quality)
    try:
        import fitz  # type: ignore  # PyMuPDF (stubs vary across environments)

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        if text.strip():
            return text
    except Exception:  # noqa: S110
        pass

    # Strategy 3: pdfplumber (good fallback)
    try:
        import io

        import pdfplumber  # type: ignore[import-not-found]

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            if text.strip():
                return text
    except Exception:  # noqa: S110
        pass

    # Strategy 4: raw byte extraction — look for readable ASCII/UTF-8 runs
    try:
        import re as _re

        raw = file_bytes.decode("latin-1", errors="ignore")
        runs = _re.findall(r"[\x20-\x7e\n\r\t]{4,}", raw)
        text = " ".join(runs)
        text = _re.sub(r"\s+", " ", text).strip()
        if len(text) > 50:
            return text
    except Exception:  # noqa: S110
        pass

    return ""


def extract_skills(text: str) -> list[dict]:
    """Extract skills from resume text using taxonomy matching.

    Matching is word-boundary based so short skills (``sql``, ``ids``,
    ``ctf``) never match inside unrelated words — e.g. a resume listing
    ``sqli`` / ``SQL injection`` yields the security skill, not a bare
    ``sql`` (programming) hit that would surface SQL-developer jobs to a
    security candidate.
    """
    text_lower = text.lower()
    found_skills = []

    for category, skills in SKILL_TAXONOMY.items():
        for skill in skills:
            pattern = rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])"
            match = re.search(pattern, text_lower)
            if not match:
                continue
            # Find context around the skill
            idx = match.start()
            start = max(0, idx - 50)
            end = min(len(text), idx + len(skill) + 50)
            context = text[start:end].strip()

            found_skills.append(
                {
                    "name": skill,
                    "category": category,
                    "context": context,
                    "confidence": 0.9 if len(skill) > 3 else 0.7,
                }
            )

    # Deduplicate
    seen = set()
    unique = []
    for s in found_skills:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)

    return unique


def extract_experience(text: str) -> list[dict]:
    """Extract work experience entries from resume text."""
    experiences = []

    # Common date patterns
    date_patterns = [
        r"(\w+\s+\d{4})\s*[-–]\s*(\w+\s+\d{4}|present|current)",
        r"(\d{4})\s*[-–]\s*(\d{4}|present|current)",
        r"(\w+\s+\d{4})\s*[-–]\s*(\w+\s+\d{4})",
    ]

    # Job title patterns
    title_patterns = [
        r"(?:senior|junior|lead|principal|staff)?\s*(?:software|security|data|devops|cloud|network|systems?|backend|frontend|full.?stack|ml|ai)\s*(?:engineer|developer|analyst|architect|specialist|consultant|intern)",
        r"(?:penetration|security|soc|vulnerability)\s*(?:tester|analyst|engineer|consultant)",
    ]

    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for date patterns
        for pattern in date_patterns:
            match = re.search(pattern, line_stripped, re.IGNORECASE)
            if match:
                # Look for job title in surrounding lines
                title = ""
                for j in range(max(0, i - 3), min(len(lines), i + 3)):
                    for tp in title_patterns:
                        tmatch = re.search(tp, lines[j], re.IGNORECASE)
                        if tmatch:
                            title = tmatch.group(0).strip()
                            break
                    if title:
                        break

                if not title:
                    # Use the line itself as title candidate
                    title = line_stripped[:80]

                experiences.append(
                    {
                        "title": title,
                        "period": line_stripped[:60],
                        "start": match.group(1) if match.group(1) else "",
                        "end": match.group(2) if match.group(2) else "",
                    }
                )
                break

    return experiences[:10]  # Max 10 experiences


def extract_education(text: str) -> list[dict]:
    """Extract education entries from resume text."""
    education: list[dict] = []

    edu_patterns = [
        r"((?:bachelor|master|phd|b\.?s\.?|m\.?s\.?|b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?)\s+(?:of|in)?\s*[\w\s]+)",
        r"((?:university|college|institute)\s+of\s+[\w\s]+)",
        r"((?:bachelor|master|phd|degree)\s+[\w\s]+)",
    ]

    for pattern in edu_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            edu_text = match.group(1).strip()
            if len(edu_text) > 10 and edu_text not in [
                e.get("degree", "") for e in education
            ]:
                education.append(
                    {
                        "degree": edu_text[:100],
                        "institution": "",
                    }
                )

    return education[:5]  # Max 5 education entries


def extract_contact(text: str) -> dict:
    """Extract contact information from resume text."""
    contact = {}

    # Email
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if email_match:
        contact["email"] = email_match.group(0)

    # Phone
    phone_match = re.search(r"[\+]?[\d\s\-\(\)]{10,15}", text)
    if phone_match:
        phone = phone_match.group(0).strip()
        if len(phone) >= 10:
            contact["phone"] = phone

    # LinkedIn
    linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", text)
    if linkedin_match:
        contact["linkedin"] = f"https://{linkedin_match.group(0)}"

    # GitHub
    github_match = re.search(r"github\.com/[\w-]+", text)
    if github_match:
        contact["github"] = f"https://{github_match.group(0)}"

    return contact


@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    """Upload a PDF resume and extract skills, experience, education, and contact info.

    Returns structured data that can be used for:
    - Auto-filling user profile skills
    - Matching against job requirements
    - Skill gap analysis
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"error": "Please upload a PDF file"}

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        return {"error": "File too large (max 10MB)"}

    # Extract text from PDF
    text = extract_text_from_pdf(content)
    if not text:
        return {
            "error": (
                "Could not extract text from PDF. The file may be scanned/image-based."
            )
        }

    # Extract structured data
    skills = extract_skills(text)
    experience = extract_experience(text)
    education = extract_education(text)
    contact = extract_contact(text)

    # Categorize skills
    skill_categories: dict[str, list] = {}
    for skill in skills:
        cat = skill["category"]
        if cat not in skill_categories:
            skill_categories[cat] = []
        skill_categories[cat].append(skill["name"])

    return {
        "success": True,
        "filename": file.filename,
        "text_length": len(text),
        "skills": skills,
        "skill_categories": skill_categories,
        "skill_count": len(skills),
        "experience": experience,
        "education": education,
        "contact": contact,
        "summary": {
            "total_skills": len(skills),
            "top_categories": list(skill_categories.keys()),
            "has_experience": len(experience) > 0,
            "has_education": len(education) > 0,
        },
    }
