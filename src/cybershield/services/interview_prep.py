"""Interview preparation question generator.

Builds a personalized shortlist of likely interview questions from the
candidate's parsed resume and a specific job posting — entirely
rule-based, so it works with zero API keys and never leaves the
platform. Questions are grouped by theme:

* **role**     — role-fit questions anchored to the job title
* **technical**— one probing question per matched skill (the skills the
  resume actually has, so every question is answerable)
* **gap**      — "be ready for" prompts about the job's skills the
  resume does not list yet (honest prep, not fabrication)
* **behavioral**— STAR-format questions any interviewer will ask
* **company**  — research questions the candidate should be ready to ask

The generator is a pure function on plain data so it is trivial to unit
test and safe to call from anywhere (API, dashboard, scheduler).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from cybershield.services.cover_letter import _as_skill_names

# Category -> question template for a matched (known) skill.
# ``{skill}`` is interpolated with the resume's own skill name so the
# candidate is asked about the tool they actually listed.
_KNOWN_SKILL_QUESTIONS: Dict[str, str] = {
    "security": "Walk me through a time you used {skill} on a real engagement — what was the goal, and how did you verify the fix?",
    "web_security": "How would you approach testing a live web app with {skill}? What's the first thing you check, and what do you never do without authorization?",
    "network_security": "Describe how you would map and harden a network using {skill} — what tools do you reach for first?",
    "cloud_security": "If you had to secure a cloud account with {skill}, what are the top five misconfigurations you'd check for?",
    "cicd_security": "Walk me through how you'd add {skill} to a CI/CD pipeline so secrets never leak and builds stay reproducible.",
    "scripting": "Write a small {skill} snippet that solves a real problem from your resume — explain your approach as you go.",
    "data_analysis": "How would you use {skill} to clean, analyze, and present a messy dataset? What pitfalls do you watch for?",
    "forensics": "Describe your process for collecting and preserving evidence with {skill} so it stays admissible in a report.",
    "recon": "How would you scope a recon phase using {skill} without crossing the legal/authorized boundary?",
    "cryptography": "When would you choose one crypto scheme over another using {skill}, and how do you handle key management?",
    "osint": "How do you use {skill} to gather intel ethically, and how do you verify the information you find?",
    "general": "Give me a concrete example of solving a problem with {skill} — what was the hardest part and how did you debug it?",
}

# Category -> question template for a job skill the resume is missing.
_MISSING_SKILL_QUESTIONS: Dict[str, str] = {
    "security": "The role lists {skill} — if you had to learn it fast, what would your first week of study look like?",
    "web_security": "Be ready to speak to {skill} even if it's not on your resume — can you explain what it does and where it fits?",
    "network_security": "Expect a question about {skill}. Prepare a one-minute overview: what it is, when you'd use it, and one gotcha.",
    "cloud_security": "Be ready for a question on {skill} — research the top misconfigurations and one real breach it caused.",
    "cicd_security": "Expect to be asked about {skill} in the pipeline — review how it fits between code, build, and deploy.",
    "scripting": "The job wants {skill} — have a small example script ready and be able to explain it line by line.",
    "data_analysis": "The role lists {skill} — prepare how you'd apply it to a business question with a small example.",
    "general": "The job lists {skill}. Read up on it and prepare one honest sentence on where you'd start.",
}

_BEHAVIORAL = [
    "Tell me about a time a project went wrong. What happened, what did you do, and what would you change?",
    "Describe a disagreement with a teammate or manager and how you resolved it.",
    "Tell me about a time you had to learn a new technology quickly to meet a deadline.",
    "Give an example of when you found a bug or vulnerability that others had missed.",
    "Describe a time you had to explain a technical topic to a non-technical audience.",
]


def _skill_category(skill: str) -> str:
    """Best-effort category for a lowercase skill name (fallback 'general')."""
    lowered = skill.lower()
    for cat in _KNOWN_SKILL_QUESTIONS:
        if cat in lowered:
            return cat
    # Common terms mapped to their category by keyword.
    if any(k in lowered for k in ("burp", "owasp", "pentest", "exploit", "sqlmap")):
        return "web_security"
    if any(k in lowered for k in ("wireshark", "nmap", "tcpdump", "firewall", "ids")):
        return "network_security"
    if any(k in lowered for k in ("aws", "azure", "gcp", "s3", "iam", "kubernetes", "docker")):
        return "cloud_security"
    if any(k in lowered for k in ("python", "bash", "powershell", "java", "go", "c++", "js")):
        return "scripting"
    if any(k in lowered for k in ("sql", "pandas", "tableau", "powerbi", "excel")):
        return "data_analysis"
    return "general"


def _known_template(skill: str) -> str:
    """Pick the matched-skill question template for a skill."""
    return _KNOWN_SKILL_QUESTIONS.get(_skill_category(skill), _KNOWN_SKILL_QUESTIONS["general"])


def _missing_template(skill: str) -> str:
    """Pick the missing-skill prompt template for a skill."""
    return _MISSING_SKILL_QUESTIONS.get(_skill_category(skill), _MISSING_SKILL_QUESTIONS["general"])


def _render(template: str, skill: str) -> str:
    """Interpolate a skill into a question template robustly.

    Uses plain string replacement (not ``str.format``) so a skill or tag
    containing literal braces (untrusted scraped data) can never crash
    the generator with a ``KeyError``/``ValueError``.
    """
    return template.replace("{skill}", skill)


def build_interview_prep(
    job_title: str,
    company: str,
    matched_skills: Optional[List[str]],
    missing_skills: Optional[List[str]],
) -> Dict[str, Any]:
    """Generate a shortlist of interview questions for one job.

    Returns a dict with ``questions`` (a list of ``{"category",
    "question"}`` dicts) and ``tips`` (actionable prep notes). The
    questions only reference skills the resume actually lists (so they
    are answerable), plus honest "be ready" prompts for the job skills
    the resume is missing.
    """
    job_title = (job_title or "this role").strip()
    company = (company or "the company").strip()

    questions: List[Dict[str, str]] = []

    # 1. Role-fit questions (2).
    questions.append(
        {
            "category": "role",
            "question": (
                f"Walk me through your background and why you're a great fit for the "
                f"{job_title} role at {company}."
            ),
        }
    )
    questions.append(
        {
            "category": "role",
            "question": (
                f"What does a successful first 90 days look like to you in a "
                f"{job_title} position at {company}?"
            ),
        }
    )

    # 2. Technical questions anchored to matched skills (max 4).
    matched = _as_skill_names(matched_skills)
    used: set[str] = set()
    for skill in matched:
        key = skill.lower()
        if key in used:
            continue
        used.add(key)
        questions.append(
            {
                "category": "technical",
                "question": _render(_known_template(skill), skill),
            }
        )
        if len(questions) >= 6:
            break

    # 3. Behavioral (2) — keep the list balanced and predictable.
    questions.extend({"category": "behavioral", "question": q} for q in _BEHAVIORAL[:2])

    # 4. Gap prompts for job skills the resume does not list (max 3).
    missing = _as_skill_names(missing_skills)
    gap_count = 0
    for skill in missing:
        key = skill.lower()
        if key in used:
            continue
        used.add(key)
        questions.append(
            {
                "category": "gap",
                "question": _render(_missing_template(skill), skill),
            }
        )
        gap_count += 1
        if gap_count >= 3:
            break

    # 5. Company research (1).
    questions.append(
        {
            "category": "company",
            "question": (
                f"What do you know about {company}'s products and mission, and what "
                f"would you ask the team in the first interview?"
            ),
        }
    )

    # Prep tips derived from the same inputs.
    tips: List[str] = []
    if matched:
        tips.append(
            f"Your resume already covers: {', '.join(matched[:5])} — prepare a "
            "concrete story for each one."
        )
    if missing:
        tips.append(
            f"The job also lists {', '.join(missing[:3])}. Spend 30 minutes on "
            "each so you can speak to them honestly."
        )
    tips.append(
        "Use the STAR format (Situation, Task, Action, Result) for every behavioral answer."
    )
    tips.append(
        f"Research {company} before the call — check their site, recent "
        "news, and the exact job description you applied to."
    )

    return {"questions": questions, "tips": tips}
