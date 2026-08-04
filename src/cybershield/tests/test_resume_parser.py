"""
Unit Tests for Resume Parser

Tests the ResumeParser class covering:
- Skill extraction from text
- Education parsing (degree, institution, GPA, years)
- Experience extraction
- Certification detection
- Project extraction
- Link detection (GitHub, LinkedIn, email, phone)
- PDF parsing (integration test)
"""

from cybershield.services.resume_service import SECURITY_SKILLS, ResumeParser


class TestResumeParserSkills:
    """Test skill extraction from text."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_extract_pentesting_skills(self):
        """Should detect penetration testing related skills."""
        text = (
            "experienced in penetration testing and ethical hacking using metasploit and burp suite"
        )
        skills = self.parser._extract_skills(text)
        skill_names = [s["name"].lower() for s in skills]
        assert "penetration testing" in skill_names
        assert "ethical hacking" in skill_names
        assert "metasploit" in skill_names
        assert "burp suite" in skill_names

    def test_extract_security_tools(self):
        """Should detect security tools."""
        text = "proficient with nmap, wireshark, and kali linux for vulnerability scanning"
        skills = self.parser._extract_skills(text)
        skill_names = [s["name"].lower() for s in skills]
        assert "nmap" in skill_names
        assert "wireshark" in skill_names
        assert "kali linux" in skill_names

    def test_extract_siem_skills(self):
        """Should detect SIEM related skills."""
        text = "experience with splunk and microsoft sentinel for log analysis and siem"
        skills = self.parser._extract_skills(text)
        skill_names = [s["name"].lower() for s in skills]
        assert "splunk" in skill_names
        assert "microsoft sentinel" in skill_names
        assert "siem" in skill_names

    def test_extract_web_security_skills(self):
        """Should detect web security skills."""
        text = "expert in xss, csrf, sql injection, and owasp top 10 testing"
        skills = self.parser._extract_skills(text)
        skill_names = [s["name"].lower() for s in skills]
        assert "xss" in skill_names
        assert "csrf" in skill_names
        assert "sql injection" in skill_names
        assert "owasp top 10" in skill_names

    def test_extract_cloud_security_skills(self):
        """Should detect cloud security skills."""
        text = "aws security and azure security experience with iam and cloudtrail"
        skills = self.parser._extract_skills(text)
        skill_names = [s["name"].lower() for s in skills]
        assert "aws security" in skill_names
        assert "azure security" in skill_names
        assert "iam" in skill_names

    def test_extract_certifications_as_skills(self):
        """Should detect certifications as skills."""
        text = "certified ethical hacker (ceh) and oscp certified"
        skills = self.parser._extract_skills(text)
        skill_names = [s["name"].lower() for s in skills]
        assert "ceh" in skill_names
        assert "oscp" in skill_names

    def test_no_skills_in_empty_text(self):
        """Should return empty list for text with no skills."""
        skills = self.parser._extract_skills("hello world nothing here")
        assert skills == []

    def test_skill_categories_are_valid(self):
        """All extracted skills should have valid categories."""
        text = "penetration testing with nmap and splunk"
        skills = self.parser._extract_skills(text)
        valid_categories = set(SECURITY_SKILLS.keys())
        for skill in skills:
            assert skill["category"] in valid_categories

    def test_skill_confidence_is_high(self):
        """All extracted skills should have high confidence."""
        text = "python scripting and bash automation"
        skills = self.parser._extract_skills(text)
        for skill in skills:
            assert skill["confidence"] >= 0.8


class TestResumeParserEducation:
    """Test education extraction."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_extract_btech_degree(self):
        """Should extract B.Tech degree."""
        text = "EDUCATION\nB.Tech in Computer Science\nUniversity of Technology\nCGPA: 8.5\n2020 - 2024"
        edu = self.parser._extract_education(text)
        assert len(edu) >= 1
        assert "b.tech" in edu[0]["degree"].lower() or "bachelor" in edu[0]["degree"].lower()

    def test_extract_institution(self):
        """Should extract institution name."""
        text = (
            "EDUCATION\nB.Tech in IT\nMahendra Engineering College, Salem\nCGPA: 6.75\n2021 - 2025"
        )
        edu = self.parser._extract_education(text)
        assert len(edu) >= 1
        assert edu[0]["institution"] is not None
        assert (
            "mahendra" in edu[0]["institution"].lower()
            or "engineering" in edu[0]["institution"].lower()
        )

    def test_extract_gpa(self):
        """Should extract GPA/CGPA."""
        text = "EDUCATION\nB.Tech in CS\nEngineering College\nCGPA: 8.5/10\n2020 - 2024"
        edu = self.parser._extract_education(text)
        assert len(edu) >= 1
        assert edu[0]["gpa"] is not None
        assert "8.5" in edu[0]["gpa"]

    def test_extract_year_range(self):
        """Should extract year range."""
        text = "EDUCATION\nB.Tech in CS\nEngineering College\nCGPA: 8.5\n2020 - 2024"
        edu = self.parser._extract_education(text)
        assert len(edu) >= 1
        assert edu[0]["years"] is not None
        assert "2020" in edu[0]["years"]
        assert "2024" in edu[0]["years"]

    def test_extract_gpa_with_suffix(self):
        """Should extract GPA with /10 suffix."""
        text = "EDUCATION\nB.Tech\nCollege\nCGPA: 6.75/10"
        edu = self.parser._extract_education(text)
        assert len(edu) >= 1
        assert "6.75" in edu[0]["gpa"]
        assert "/10" in edu[0]["gpa"]

    def test_no_education_returns_empty(self):
        """Should return empty list when no education found."""
        edu = self.parser._extract_education("no education info here")
        assert edu == []


class TestResumeParserExperience:
    """Test experience extraction."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_extract_intern_role(self):
        """Should detect intern roles."""
        text = "WORK EXPERIENCE\nSecurity Intern at Tech Corp\nWorked on vulnerability assessment"
        exp = self.parser._extract_experience(text)
        roles = [e["role"].lower() for e in exp]
        assert "intern" in roles

    def test_extract_analyst_role(self):
        """Should detect analyst roles."""
        text = "EXPERIENCE\nSOC Analyst at CyberSec Inc\nMonitoring security events"
        exp = self.parser._extract_experience(text)
        roles = [e["role"].lower() for e in exp]
        assert "analyst" in roles

    def test_extract_engineer_role(self):
        """Should detect engineer roles."""
        text = "EXPERIENCE\nSecurity Engineer at Company\nBuilding secure systems"
        exp = self.parser._extract_experience(text)
        roles = [e["role"].lower() for e in exp]
        assert "engineer" in roles

    def test_experience_deduplication(self):
        """Should deduplicate same roles."""
        text = "Intern at Company A\nIntern at Company B\nIntern at Company C"
        exp = self.parser._extract_experience(text)
        roles = [e["role"].lower() for e in exp]
        assert roles.count("intern") == 1

    def test_experience_has_context(self):
        """Each experience should have context."""
        text = "Security Intern at Tech Corp doing vulnerability assessments"
        exp = self.parser._extract_experience(text)
        assert len(exp) >= 1
        assert exp[0]["context"] is not None
        assert len(exp[0]["context"]) > 0


class TestResumeParserCertifications:
    """Test certification extraction."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_extract_ceh(self):
        """Should detect CEH certification."""
        text = "CERTIFICATIONS\nCertified Ethical Hacker (CEH) - Completed"
        certs = self.parser._extract_certifications(text)
        cert_names = [c["name"].lower() for c in certs]
        assert "ceh" in cert_names

    def test_extract_oscp(self):
        """Should detect OSCP certification."""
        text = "CERTIFICATIONS\nOffensive Security Certified Professional (OSCP)"
        certs = self.parser._extract_certifications(text)
        cert_names = [c["name"].lower() for c in certs]
        assert "oscp" in cert_names

    def test_extract_security_plus(self):
        """Should detect Security+ certification."""
        text = "CERTIFICATIONS\nCompTIA Security+ - In Progress"
        certs = self.parser._extract_certifications(text)
        cert_names = [c["name"].lower() for c in certs]
        assert any("security" in name for name in cert_names)

    def test_certification_status_in_progress(self):
        """Should detect in progress status."""
        text = "CERTIFICATIONS\nCEH - In Progress"
        certs = self.parser._extract_certifications(text)
        assert len(certs) >= 1
        assert any(c["status"] == "in progress" for c in certs)

    def test_certification_status_completed(self):
        """Should detect completed status."""
        text = "CERTIFICATIONS\nCEH - Completed"
        certs = self.parser._extract_certifications(text)
        assert len(certs) >= 1
        completed = [c for c in certs if c["status"] == "completed"]
        assert len(completed) >= 1


class TestResumeParserProjects:
    """Test project extraction."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_extract_projects_section(self):
        """Should extract projects from PROJECTS section."""
        text = """PROJECTS
- Network Vulnerability Assessment using Nessus and Nmap
- DVWA Security Testing with Burp Suite
- PortSwigger SQL Injection Labs
"""
        projects = self.parser._extract_projects(text)
        assert len(projects) >= 2

    def test_project_has_name(self):
        """Each project should have a name."""
        text = "PROJECTS\n- Metasploitable 2 Vulnerability Testing"
        projects = self.parser._extract_projects(text)
        assert len(projects) >= 1
        assert projects[0]["name"] is not None
        assert len(projects[0]["name"]) > 0

    def test_project_has_technologies(self):
        """Projects should detect mentioned technologies."""
        text = "PROJECTS\n- DVWA Testing using Burp Suite and OWASP"
        projects = self.parser._extract_projects(text)
        assert len(projects) >= 1
        techs = [t.lower() for t in projects[0]["technologies"]]
        assert any("burp" in t for t in techs)

    def test_no_projects_returns_empty(self):
        """Should return empty list when no projects found."""
        projects = self.parser._extract_projects("no projects here")
        assert projects == []


class TestResumeParserLinks:
    """Test link extraction."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_extract_github(self):
        """Should extract GitHub profile URL."""
        text = "GitHub: https://github.com/username"
        links = self.parser._extract_links(text)
        assert "github" in links
        assert "github.com" in links["github"]

    def test_extract_linkedin(self):
        """Should extract LinkedIn profile URL."""
        text = "LinkedIn: https://linkedin.com/in/johndoe"
        links = self.parser._extract_links(text)
        assert "linkedin" in links
        assert "linkedin.com" in links["linkedin"]

    def test_extract_email(self):
        """Should extract email address."""
        text = "Contact: john.doe@example.com"
        links = self.parser._extract_links(text)
        assert "email" in links
        assert "john.doe@example.com" in links["email"]

    def test_extract_phone(self):
        """Should extract phone number."""
        text = "Phone: +1 555 123 4567"
        links = self.parser._extract_links(text)
        assert "phone" in links

    def test_extract_tryhackme(self):
        """Should extract TryHackMe profile URL."""
        text = "TryHackMe: https://tryhackme.com/p/username"
        links = self.parser._extract_links(text)
        assert "tryhackme" in links

    def test_no_links_returns_empty(self):
        """Should return empty dict when no links found."""
        links = self.parser._extract_links("no links here")
        assert links == {}

    def test_multiple_links(self):
        """Should extract multiple link types."""
        text = """
GitHub: https://github.com/user
LinkedIn: https://linkedin.com/in/user
Email: user@test.com
Phone: +91 9876543210
"""
        links = self.parser._extract_links(text)
        assert "github" in links
        assert "linkedin" in links
        assert "email" in links
        assert "phone" in links


class TestResumeParserFlattenSkills:
    """Test skill flattening."""

    def test_all_skills_flattened(self):
        """Should flatten all security skills into a single dict.
        Note: Some keywords appear in multiple categories (e.g., 'burp suite'
        in both pentesting and security_tools), so the flattened dict may have
        fewer entries than the total count due to deduplication."""
        parser = ResumeParser()
        total_entries = sum(len(skills) for skills in SECURITY_SKILLS.values())
        unique_skills = len(parser._all_skills)
        # Unique skills should be <= total entries (due to cross-category duplicates)
        # and at least 80% of total (not too many duplicates)
        assert unique_skills <= total_entries
        assert unique_skills >= total_entries * 0.8

    def test_skill_mapping_is_correct(self):
        """Each skill should map to its correct category."""
        parser = ResumeParser()
        assert parser._all_skills["nmap"] == "security_tools"
        assert parser._all_skills["metasploit"] == "security_tools"
        assert parser._all_skills["python"] == "scripting"
        assert parser._all_skills["siem"] == "siem"


class TestResumeParserFullParse:
    """Test full text parsing."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_full_parse_returns_all_fields(self):
        """Full parse should return all expected fields."""
        text = """
John Doe
john@example.com | +91 9876543210
GitHub: https://github.com/johndoe
LinkedIn: https://linkedin.com/in/johndoe

EDUCATION
B.Tech in Information Technology
Mahendra Engineering College, Salem
CGPA: 6.75/10
2021 - 2025

SKILLS
Penetration Testing, Nmap, Burp Suite, Metasploit
Python, Bash scripting
OWASP Top 10, SQL Injection, XSS

EXPERIENCE
Security Intern at Tech Corp
Vulnerability assessment and penetration testing

PROJECTS
- DVWA Security Testing using Burp Suite
- Network Scanning with Nmap

CERTIFICATIONS
CEH - Completed
"""
        result = self.parser._parse_text(text, "test_resume.pdf")

        assert "skills" in result
        assert "education" in result
        assert "experience" in result
        assert "certifications" in result
        assert "projects" in result
        assert "links" in result
        assert "raw_text" in result
        assert "parsed_at" in result

    def test_full_parse_extracts_skills(self):
        """Full parse should extract multiple skills."""
        text = "penetration testing with nmap and metasploit using python scripting"
        result = self.parser._parse_text(text)
        assert len(result["skills"]) >= 3

    def test_full_parse_extracts_links(self):
        """Full parse should extract links."""
        text = """
GitHub: https://github.com/user
Email: user@test.com
"""
        result = self.parser._parse_text(text)
        assert "github" in result["links"]
        assert "email" in result["links"]

    def test_full_parse_extracts_education(self):
        """Full parse should extract education."""
        text = "EDUCATION\nB.Tech in CS\nUniversity\nCGPA: 8.0\n2020 - 2024"
        result = self.parser._parse_text(text)
        assert len(result["education"]) >= 1

    def test_full_parse_extracts_experience(self):
        """Full parse should extract experience."""
        text = "EXPERIENCE\nSecurity Intern at Company"
        result = self.parser._parse_text(text)
        assert len(result["experience"]) >= 1

    def test_full_parse_extracts_projects(self):
        """Full parse should extract projects."""
        text = "PROJECTS\n- Project A using Nmap and Metasploit\n- Project B with Burp Suite"
        result = self.parser._parse_text(text)
        assert len(result["projects"]) >= 1

    def test_full_parse_extracts_certifications(self):
        """Full parse should extract certifications."""
        text = "CERTIFICATIONS\nCEH - Completed\nOSCP - In Progress"
        result = self.parser._parse_text(text)
        assert len(result["certifications"]) >= 1


class TestResumeParserPdfFallback:
    """Test the pure-stdlib PDF fallback extractor (used on Vercel).

    pymupdf is not installed on Vercel's runtime, so the fallback must
    handle ASCII85 + FlateDecode streams and plain zlib streams using
    only the standard library. These tests build a minimal PDF in memory
    and verify text extraction without requiring pymupdf.
    """

    def setup_method(self):
        self.parser = ResumeParser()

    def _build_a85_flate_pdf(self, text: str) -> bytes:
        """Build a minimal PDF whose content stream is ASCII85+Flate encoded."""
        import base64
        import zlib

        content = f"BT /F1 12 Tf 14.4 TL ET\nBT 1 0 0 1 50 750 Tm ({text}) Tj T* ET\n"
        compressed = zlib.compress(content.encode("latin-1"))
        a85 = base64.a85encode(compressed)
        stream = a85 + b"~>"
        length = len(stream)
        pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
            b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            b"4 0 obj\n<< /Filter [ /ASCII85Decode /FlateDecode ] /Length "
            + str(length).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream\nendobj\n"
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"trailer\n<< /Size 6 /Root 1 0 R >>\n%%EOF\n"
        )
        return pdf

    def test_a85_flate_fallback_extracts_text(self, tmp_path):
        """Fallback must extract text from ASCII85+Flate encoded streams."""
        pdf = self._build_a85_flate_pdf("Python penetration testing Nmap Burp Suite")
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(pdf)

        text = self.parser._extract_pdf_text(str(pdf_path))
        assert "Python" in text
        assert "penetration testing" in text

    def test_a85_flate_fallback_no_endstream_whitespace(self, tmp_path):
        """Fallback must handle streams where data ends flush at 'endstream'."""
        import base64
        import zlib

        content = "BT /F1 12 Tf 14.4 TL ET\nBT 1 0 0 1 50 750 Tm (Nmap) Tj ET\n"
        stream = base64.a85encode(zlib.compress(content.encode("latin-1"))) + b"~>"
        pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
            b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            b"4 0 obj\n<< /Filter [ /ASCII85Decode /FlateDecode ] /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"endstream\nendobj\n"
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"trailer\n<< /Size 6 /Root 1 0 R >>\n%%EOF\n"
        )
        pdf_path = tmp_path / "resume2.pdf"
        pdf_path.write_bytes(pdf)

        text = self.parser._extract_pdf_text(str(pdf_path))
        assert "Nmap" in text

    def test_plain_zlib_fallback(self, tmp_path):
        """Fallback must handle plain zlib (FlateDecode only) streams."""
        import zlib

        content = "BT /F1 12 Tf 14.4 TL ET\nBT 1 0 0 1 50 750 Tm (Wireshark) Tj ET\n"
        stream = zlib.compress(content.encode("latin-1"))
        pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
            b"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            b"4 0 obj\n<< /Filter /FlateDecode /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream\nendobj\n"
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"trailer\n<< /Size 6 /Root 1 0 R >>\n%%EOF\n"
        )
        pdf_path = tmp_path / "resume3.pdf"
        pdf_path.write_bytes(pdf)

        text = self.parser._extract_pdf_text(str(pdf_path))
        assert "Wireshark" in text

    def test_garbage_stream_does_not_crash(self, tmp_path):
        """Fallback must not raise on malformed stream data."""
        pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
            b"   /Contents 4 0 R >>\nendobj\n"
            b"4 0 obj\n<< /Length 20 >>\nstream\nNOT-REAL-DATA-123\nendstream\nendobj\n"
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"trailer\n<< /Size 6 /Root 1 0 R >>\n%%EOF\n"
        )
        pdf_path = tmp_path / "resume4.pdf"
        pdf_path.write_bytes(pdf)

        text = self.parser._extract_pdf_text(str(pdf_path))
        assert isinstance(text, str)

    def test_parse_upload_extracts_skills_without_pymupdf(self, tmp_path):
        """parse_upload should extract skills via fallback when pymupdf missing."""
        pdf = self._build_a85_flate_pdf("Python Nmap Metasploit SIEM")
        pdf_path = tmp_path / "resume5.pdf"
        pdf_path.write_bytes(pdf)

        import asyncio

        result = asyncio.run(self.parser.parse_upload(pdf, "resume5.pdf"))
        names = [s["name"].lower() for s in result["skills"]]
        assert "python" in names
        assert "nmap" in names


# Real resume (VAPT fresher) text — the exact content extracted from the
# user's "Parthasarathi_B_VAPT_Resume_Final" PDF. Used to lock in detection
# quality regressions.
REAL_RESUME_TEXT = """\
PARTHASARATHI B
parthasarathi442004@gmail.com
+91 6380319830
Bangalore, Karnataka
https://linkedin.com/in/parthasarathi-b-24b986267
https://tryhackme.com/p/parthasarathi442
PROFESSIONAL SUMMARY
Disciplined and motivated IT graduate with NCC background and CEH/CSA training.
Strong interest in cybersecurity with proficiency in vulnerability assessment,
OWASP Top 10, and exploitation using Kali Linux, Nmap, Nessus, Metasploit, and
Burp Suite. Hands-on experience with Metasploitable 2, DVWA, and PortSwigger labs.
TECHNICAL SKILLS
Vulnerability Assessment: Nessus, OpenVAS, CVSS Scoring, Risk Rating
Penetration Testing: Network Pentesting, Web App Testing, OWASP Top 10, Exploitation
Security Tools: Nmap, Metasploit, Burp Suite, Wireshark, Kali Linux, Hydra, OWASP ZAP
Reconnaissance: Passive Recon, Active Recon, Google Dorks, Shodan
Privilege Escalation: Linux Privesc, Windows Privesc, SUID Exploits
HANDS-ON LABS
Network Vulnerability Assessment using Nessus and Nmap on Metasploitable 2
Web Application Security Testing on DVWA using Burp Suite and OWASP ZAP
SQL Injection labs on PortSwigger Web Security Academy
PROJECTS
Vulnerability Assessment - Metasploitable (192.168.1.82)
February 2026
• Conducted VA using Nessus Scanner, identified 122 vulnerabilities
• Documented critical findings: VNC weak password (CVSS 10.0)
Penetration Testing - Metasploitable 2 (192.168.1.68)
May 2026
• Performed reconnaissance using Nmap, identified 7 open ports
• Exploited bindshell on port 1524 using Netcat
CERTIFICATION
CEH v13 with AI & SOC Analyst Training
In Progress / TechByHeart Academy
EDUCATION
Mahendra Engineering College, Salem - B.Tech in Information Technology
2021 - 2025 / CGPA: 6.75/10
ADDITIONAL
NCC Cadet - Team leadership and disciplined execution
"""


class TestResumeParserRealResume:
    """Quality checks against the user's real VAPT resume."""

    def setup_method(self):
        self.parser = ResumeParser()

    def test_real_resume_full_parse(self):
        """Full parse of the real resume returns all sections."""
        result = self.parser._parse_text(REAL_RESUME_TEXT, "real_resume.pdf")
        assert "skills" in result
        assert "education" in result
        assert "projects" in result
        assert "certifications" in result
        assert "links" in result

    def test_real_resume_skills_quality(self):
        """Skills are extracted with no false positives from word boundaries."""
        result = self.parser._parse_text(REAL_RESUME_TEXT)
        names = [s["name"].lower() for s in result["skills"]]
        # Key skills present.
        for skill in ("nessus", "nmap", "metasploit", "burp suite", "kali linux"):
            assert skill in names
        # Short-keyword false positives must NOT appear ("go" in Google,
        # "dd" in Conducted, "ids" inside other words, etc.).
        assert "go" not in names
        assert "dd" not in names

    def test_real_resume_projects_quality(self):
        """Only the two real projects are extracted (not labs/competencies)."""
        result = self.parser._parse_text(REAL_RESUME_TEXT)
        projects = result["projects"]
        assert len(projects) == 2
        names = " ".join(p["name"] for p in projects).lower()
        assert "vulnerability assessment" in names
        assert "penetration testing" in names

    def test_real_resume_no_fake_experience(self):
        """No fake work experience from prose (Analyst/Engineer/Cadet/lead)."""
        result = self.parser._parse_text(REAL_RESUME_TEXT)
        # This resume has no professional experience section, so nothing
        # should be detected — "SOC Analyst Training", "Engineering College",
        # "Team leadership" are all prose, not roles.
        assert result["experience"] == []

    def test_real_resume_links_quality(self):
        """Links are clean — no bare platform URL in 'portfolio'."""
        result = self.parser._parse_text(REAL_RESUME_TEXT)
        links = result["links"]
        assert links["linkedin"].startswith("https://linkedin.com/in/")
        assert links["tryhackme"].startswith("https://tryhackme.com/p/")
        assert "email" in links
        # portfolio must not be a bare linkedin/github/tryhackme domain.
        if "portfolio" in links:
            assert "linkedin.com" not in links["portfolio"]
            assert "tryhackme.com" not in links["portfolio"]

    def test_real_resume_education_quality(self):
        """Education is parsed precisely from the real resume."""
        result = self.parser._parse_text(REAL_RESUME_TEXT)
        assert len(result["education"]) >= 1
        edu = result["education"][0]
        assert edu["degree"] is not None
        assert "b.tech" in edu["degree"].lower()
        assert edu["institution"] is not None
        assert "mahendra" in edu["institution"].lower()

    def test_real_resume_certifications(self):
        """CEH certification detected from the real resume."""
        result = self.parser._parse_text(REAL_RESUME_TEXT)
        names = [c["name"].lower() for c in result["certifications"]]
        assert "ceh" in names

    def test_project_title_plus_bullets_layout(self):
        """Title+bullets layout (real resume style) groups details correctly."""
        text = """PROJECTS
Vulnerability Assessment - Metasploitable (192.168.1.82)
February 2026
• Conducted VA using Nessus Scanner
• Documented critical findings: VNC weak password (CVSS 10.0)
Penetration Testing - Metasploitable 2 (192.168.1.68)
May 2026
• Performed reconnaissance using Nmap
"""
        projects = self.parser._extract_projects(text)
        assert len(projects) == 2
        p0 = projects[0]
        assert "vulnerability assessment" in p0["name"].lower()
        # Details belong to the first project.
        assert "nessus" in p0["description"].lower()

    def test_bullet_list_layout(self):
        """Plain bullet list (each bullet = its own project)."""
        text = """PROJECTS
- Network Vulnerability Assessment using Nessus and Nmap
- DVWA Security Testing with Burp Suite
- PortSwigger SQL Injection Labs
"""
        projects = self.parser._extract_projects(text)
        assert len(projects) == 3

    def test_hands_on_labs_not_projects(self):
        """HANDS-ON LABS / KEY COMPETENCIES sections must not be projects."""
        text = """HANDS-ON LABS
- Network Vulnerability Assessment using Nessus
- SQL Injection labs on PortSwigger
KEY COMPETENCIES
- Port scanning and service enumeration using Nmap
PROJECTS
- DVWA Security Testing using Burp Suite
"""
        projects = self.parser._extract_projects(text)
        assert len(projects) == 1
        assert "dvwa" in projects[0]["name"].lower()

    def test_portfolio_excludes_platform_domains(self):
        """portfolio never captures a bare known-platform domain."""
        text = "LinkedIn: https://linkedin.com/in/user\nGitHub: https://github.com/user"
        links = self.parser._extract_links(text)
        assert "portfolio" not in links
        assert "linkedin" in links
        assert "github" in links

    def test_custom_portfolio_domain_still_detected(self):
        """A genuine custom domain is still detected as portfolio."""
        text = "Portfolio: https://parthasarathi.dev"
        links = self.parser._extract_links(text)
        assert "portfolio" in links
        assert "parthasarathi.dev" in links["portfolio"]

    def test_experience_word_boundary_no_false_positives(self):
        """Role keywords must not match inside other words or 'X Training'."""
        text = (
            "SOC Analyst Training at TechByHeart\n"
            "Mahendra Engineering College, Salem\n"
            "NCC Cadet - Team leadership\n"
            "Worked on vulnerability scanning\n"
        )
        exp = self.parser._extract_experience(text)
        # "analyst" inside "Analyst Training" (course name, not a role),
        # "engineer" inside "Engineering", "lead" inside "leadership" —
        # none should match.
        roles = [e["role"].lower() for e in exp]
        assert roles == []

    def test_tj_array_fragments_joined_with_word_gaps(self):
        """TJ-array fragments are joined, inserting spaces at word gaps."""
        body = "(P)100(AR)20(THASARA)90(THI)-278(B)"
        text = ResumeParser._join_tj_fragments(body)
        assert text == "PARTHASARATHI B"

    def test_tj_array_pdf_escapes_unescaped(self):
        """PDF octal/backslash escapes inside TJ fragments are unescaped."""
        text = ResumeParser._join_tj_fragments(r"(pro\002ciency)")
        # \002 is an octal escape → control char; no literal backslash remains.
        assert "\\" not in text
        assert text.replace("\x02", "") == "prociency"

    def test_tj_array_escape_slash(self):
        """A lone escaped backslash (\\\\ in PDF) unescapes to one slash."""
        text = ResumeParser._join_tj_fragments(r"(a\\b)")
        assert text == r"a\b" or text == "ab"

    def test_data_analyst_resume_skills_and_projects(self):
        """A non-security resume still extracts skills, projects and certs."""
        text = """DATA ANALYST
email@x.com
OBJECTIVES
Motivated Data Analyst with skills in Python, SQL, Excel, Power BI.
EDUCATION
Bachelor of Engineering Computer Science Keystone School of
Engineering, Pune - 2026 | CGPA 7 th sem : 8.65
SKILLS
Technical Skills:
Advanced Excel: VLOOKUP, Pivot Table
SQL: Joins, Window Functions
Power BI: DAX, Power Query
Tools: Microsoft Excel, MySQL, jupyter Notebook
PROJECTS
Pizza Sales Dashboard (Power BI)
- Built an interactive dashboard using Power BI, DAX
- Visualized total sales and Purchase Trends
Employee Salary System (MySQL)
- Automated salary management using MySQL
CERTIFICATES
Certificate of Advanced Excel
Certificate of SQL Mastery
"""
        result = self.parser._parse_text(text)
        skill_names = {s["name"].lower() for s in result["skills"]}
        assert "python" in skill_names
        assert "sql" in skill_names
        assert "power bi" in skill_names
        assert "excel" in skill_names
        assert "mysql" in skill_names
        assert "dax" in skill_names

        projects = result["projects"]
        assert len(projects) == 2
        assert "pizza sales" in projects[0]["name"].lower()
        assert "employee salary" in projects[1]["name"].lower()

        edu = result["education"]
        assert edu and "bachelor" in edu[0]["degree"].lower()
        assert "keystone" in (edu[0]["institution"] or "").lower()
        assert edu[0]["gpa"] == "8.65"

        cert_names = {c["name"].lower() for c in result["certifications"]}
        assert "advanced excel" in cert_names
        assert "sql mastery" in cert_names

    def test_symbol_font_bullets_normalized(self):
        """\uf0b7 (Symbol font) bullets are normalized to \u2022."""
        text = "PROJECTS\n\uf0b7 Pizza Dashboard (Power BI)\n- Built it\n\uf0b7 Sales Tracker (Excel)\n- Tracked sales\n"
        projects = self.parser._extract_projects(text)
        assert len(projects) == 2
        assert "pizza dashboard" in projects[0]["name"].lower()

    def test_linkedin_www_prefix(self):
        """www.linkedin.com URLs are detected."""
        text = "LinkedIn: https://www.linkedin.com/in/dnyaneshwari-vanjari"
        links = self.parser._extract_links(text)
        assert links.get("linkedin") == "https://www.linkedin.com/in/dnyaneshwari-vanjari"

    def test_certificate_of_generic_lines(self):
        """'Certificate of X' lines are captured for non-security resumes."""
        text = "CERTIFICATES\nCertificate of Advanced Excel - completed\nCertificate of SQL Mastery - completed\n"
        certs = self.parser._extract_certifications(text)
        names = {c["name"].lower() for c in certs}
        assert "advanced excel" in names
        assert "sql mastery" in names

    def test_education_single_line_year_does_not_bleed(self):
        """Degree stops at the year even when the whole block is one line."""
        text = (
            "EDUCATION\n"
            "Mahendra Engineering College, Salem - B.Tech in Information "
            "Technology 2021 - 2025 \\ CGPA: 6.75/10\n"
        )
        edu = self.parser._extract_education(text)
        assert len(edu) >= 1
        assert edu[0]["degree"] == "B.Tech in Information Technology"
        assert edu[0]["gpa"] == "6.75/10"
        assert edu[0]["years"] == "2021 - 2025"

    def test_projects_no_bullets_short_title_heuristic(self):
        """PDF-style projects (no bullets) use short-title heuristic."""
        text = """PROJECTS
Vulnerability Assessment - Metasploitable (192.168.1.82)
February 2026
Conducted VA using Nessus Scanner, identified 122 vulnerabilities
Documented critical findings: VNC weak password (CVSS 10.0)
Report: https://www.mediafire.com/file/abc
Penetration Testing - Metasploitable 2 (192.168.1.68)
May 2026
Performed reconnaissance using Nmap, identified 7 open ports
"""
        projects = self.parser._extract_projects(text)
        assert len(projects) == 2
        names = " ".join(p["name"] for p in projects).lower()
        assert "vulnerability assessment" in names
        assert "penetration testing" in names
        # Detail lines belong to the first project's description.
        assert "nessus" in projects[0]["description"].lower()
