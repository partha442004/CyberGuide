"""Cover letter generator.

Builds a personalized, tailored cover letter from the candidate's parsed
resume and a specific job posting — entirely rule-based, so it works with
zero API keys and never leaves the platform. The output is honest: it
highlights the candidate's matched skills, names the company and role,
and gently surfaces the skills the job wants that the resume should
emphasize (so the letter is a guide, not a fabrication).

The generator is a pure function on plain data so it is trivial to unit
test and safe to call from anywhere (API, dashboard, scheduler).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _as_skill_names(skills: Any) -> List[str]:
    """Normalize a skills list (strings or dicts with ``name``) to names."""
    names: List[str] = []
    for s in skills or []:
        if isinstance(s, str) and s.strip():
            names.append(s.strip())
        elif isinstance(s, dict):
            name = str(s.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _top_skills(
    skill_names: List[str],
    matched: Optional[List[str]],
    limit: int = 6,
) -> List[str]:
    """Choose the letter's headline skills: matched ones first, then the rest."""
    lower = {s.lower() for s in skill_names}
    if matched:
        ordered = [s for s in matched if s.lower() in lower]
        ordered += [
            s for s in skill_names if s.lower() not in {x.lower() for x in ordered}
        ]
    else:
        # Sort for deterministic output (inputs may be sets/dicts).
        ordered = sorted(skill_names, key=str.lower)
    seen: set[str] = set()
    out: List[str] = []
    for s in ordered:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= limit:
            break
    return out


def build_cover_letter(
    resume_skills: Any,
    job_title: str,
    company: str,
    matched_skills: Optional[List[str]] = None,
    resume_name: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a tailored cover letter (plain text, 3 paragraphs).

    Parameters mirror what the resume matcher already computes so the
    letter's claims stay consistent with the match score.
    """
    skills = _top_skills(_as_skill_names(resume_skills), matched_skills)
    job_title = (job_title or "this role").strip()
    company = (company or "your company").strip()
    salutation = f"Dear {company} Hiring Team,"

    skills_line = ", ".join(skills) if skills else "a strong foundation in this domain"
    matched_line = ""
    if matched_skills:
        names = ", ".join(matched_skills[:5])
        matched_line = (
            f" My background maps directly onto what this role needs — "
            f"{names} — and I am excited to put those skills to work."
        )

    intro = (
        f"I am writing to apply for the {job_title} position at {company}."
        f" As someone who has been following {company}'s work, I am excited "
        f"about the chance to contribute to your team."
    )

    body = (
        f"I bring hands-on experience with {skills_line}.{matched_line} "
        f"I enjoy taking ownership of problems end-to-end: researching the "
        f"right approach, implementing it cleanly, and learning from the "
        f"outcome. I am particularly motivated by work that has a real impact, "
        f"and I believe {company}'s mission creates exactly that kind of work."
    )

    closing = (
        f"I would welcome the opportunity to discuss how my experience "
        f"aligns with {company}'s goals. Thank you for your time and "
        f"consideration."
    )

    name_line = resume_name or "—"

    letter = f"{salutation}\n\n{intro}\n\n{body}\n\n{closing}\n\nBest regards,\n{name_line}"
    return letter
