"""Domain classification tests.

Covers ``_classify_job`` — the keyword-driven grouping that feeds the
``/domains`` endpoints and the dashboard's category sections. The
cybersecurity keyword list must catch common offensive/defensive terms
(SQLi, XSS, VAPT, SOC, malware, devsecops ...) so security jobs land in
the Cybersecurity section instead of being lumped into Development.
"""

from interntrack.api.v1.domains import DOMAINS, _classify_job


class TestCybersecurityClassification:
    """Security-flavoured jobs must classify as cybersecurity."""

    def test_vapt_engineer(self):
        domains = _classify_job(
            "Vulnerability Assessment and Penetration Testing Engineer",
            "Perform VAPT, web application security assessments with "
            "Burp Suite and OWASP.",
            ["security", "vapt"],
        )
        assert "cybersecurity" in domains

    def test_sqli_appsec_job(self):
        domains = _classify_job(
            "Application Security Engineer",
            "Find SQL injection, XSS and CSRF bugs. Threat modeling and "
            "secure code review.",
            ["appsec", "exploit"],
        )
        assert "cybersecurity" in domains

    def test_soc_analyst(self):
        domains = _classify_job(
            "SOC Analyst L1",
            "Monitor SIEM alerts, respond to incidents, threat hunting.",
            ["soc", "siem"],
        )
        assert "cybersecurity" in domains

    def test_incident_response_analyst(self):
        domains = _classify_job(
            "Incident Response Analyst",
            "Malware analysis, digital forensics and incident response.",
            [],
        )
        assert "cybersecurity" in domains

    def test_devsecops_engineer(self):
        domains = _classify_job(
            "DevSecOps Engineer",
            "Embed security in CI/CD pipelines, SAST/DAST, cloud security.",
            ["devsecops"],
        )
        assert "cybersecurity" in domains


class TestDevelopmentClassification:
    """Plain coding jobs must NOT leak into cybersecurity."""

    def test_python_developer(self):
        domains = _classify_job(
            "Senior Python Developer",
            "Build REST APIs with FastAPI and a React frontend.",
            ["python", "react"],
        )
        assert "cybersecurity" not in domains
        assert "development" in domains

    def test_data_analyst(self):
        domains = _classify_job(
            "Data Analyst",
            "SQL queries, dashboards and machine learning pipelines.",
            ["data", "analytics"],
        )
        assert "cybersecurity" not in domains

    def test_empty_signals_fall_back_to_development(self):
        assert _classify_job("", None, []) == ["development"]


class TestKeywordCoverage:
    """The cybersecurity keyword list must include web-app/offensive terms."""

    def test_cybersecurity_keywords_cover_webapp_terms(self):
        # Scoped to the cybersecurity list itself (not all domains) so a
        # term moved to the wrong domain would fail this test.
        kws = " ".join(DOMAINS["cybersecurity"]["keywords"])
        for term in (
            "sqli",
            "sql injection",
            "xss",
            "csrf",
            "exploit",
            "malware",
            "ransomware",
            "phishing",
            "devsecops",
            "appsec",
            "red team",
            "blue team",
            "threat hunting",
            "bug bounty",
            "iso 27001",
        ):
            assert term in kws, f"cybersecurity keyword list missing {term!r}"
