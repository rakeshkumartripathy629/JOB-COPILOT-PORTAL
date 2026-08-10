"""Deterministic resume-to-job matching.

Every score is 0-100 and is computed from resume/profile evidence only — no LLM, no
hallucinated skills. Scores are stable so the same job always produces the same result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.job_enrichment_service import extract_skills
from app.services.search_profile_service import SearchProfile

#: Skills that are core engineering requirements (missing these is a critical mismatch).
CORE_TECH_SKILLS = {
    "python", "java", "javascript", "typescript", "node", "node.js", "react", "angular",
    "go", "golang", "c++", "c#", "ruby", "php", "sql", "postgres", "mysql",
    "mongodb", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux",
    "html", "css", "rest", "graphql", "django", "flask", "fastapi", "spring", "sap",
    "salesforce", "swift", "kotlin", "flutter", "android", "ios", "tensorflow",
    "pytorch", "spark", "kafka", "redis", "git", "ci/cd", "machine learning", "ml",
    "deep learning", "nlp", "data engineering", "etl", "devops", "sre",
}

#: Soft skills are never counted as "critical missing".
SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "collaboration", "agile", "scrum",
    "problem solving", "time management", "presentation", "stakeholder management",
    "mentorship", "analytical skills", "detail oriented", "multitasking",
}

SENIORITY_LEVELS = {
    "Intern": 1, "Junior": 2, "Associate": 2, "Mid-level": 3, "Senior": 4,
    "Staff": 5, "Principal": 5, "Lead": 5, "Manager": 5,
    "Head": 6, "Director": 6, "VP": 7, "Executive": 7,
}


@dataclass
class MatchResult:
    overall_score: int
    skill_score: int
    experience_score: int
    seniority_score: int
    location_score: int
    salary_score: int
    responsibility_score: int
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    critical_missing: list[str] = field(default_factory=list)
    related_skills: list[str] = field(default_factory=list)
    recommendation: str = "No Recommendation"

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "skill_score": self.skill_score,
            "experience_score": self.experience_score,
            "seniority_score": self.seniority_score,
            "location_score": self.location_score,
            "salary_score": self.salary_score,
            "responsibility_score": self.responsibility_score,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "critical_missing": self.critical_missing,
            "related_skills": self.related_skills,
            "recommendation": self.recommendation,
        }


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> int:
    return max(int(low), min(int(high), round(value)))


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]", " ", text.lower())


def match_job(
    *,
    profile: SearchProfile,
    title: str,
    description: str | None = None,
    requirements: str | None = None,
    skills: list[str] | None = None,
    experience_min: int | None = None,
    experience_max: int | None = None,
    seniority: str | None = None,
    location: str | None = None,
    country: str | None = None,
    remote_type: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    resume_text: str = "",
) -> MatchResult:
    profile_skills = {_norm(s) for s in profile.skills if s}
    title_text = _norm(title)
    body = _norm(" ".join(filter(None, [description, requirements])))
    job_text = f"{title_text} {body}"

    if skills:
        job_skills = [_norm(s) for s in skills if s]
    else:
        job_skills = [_norm(s) for s in extract_skills(f"{title} {description or ''} {requirements or ''}")]

    matched = sorted({s for s in job_skills if s in profile_skills})
    missing = sorted({s for s in job_skills if s not in profile_skills})
    critical_missing = sorted({s for s in missing if s in CORE_TECH_SKILLS})

    skill_score = _clamp(100 * len(matched) / len(job_skills)) if job_skills else 50
    years = profile.experience_years
    if years is None:
        experience_score = 50
    elif experience_min is not None and experience_max is not None:
        if experience_min <= years <= experience_max:
            experience_score = 100
        elif years < experience_min:
            gap = experience_min - years
            experience_score = _clamp(100 - gap * 12, low=15)
        else:
            experience_score = 80
    elif experience_min is not None:
        experience_score = 100 if years >= experience_min else _clamp(100 - (experience_min - years) * 12, low=15)
    elif experience_max is not None:
        experience_score = 100 if years <= experience_max else _clamp(100 - (years - experience_max) * 12, low=40)
    else:
        experience_score = 70

    profile_level = SENIORITY_LEVELS.get(profile.seniority or "")
    job_level = SENIORITY_LEVELS.get(seniority or "")
    if profile_level is None or job_level is None:
        seniority_score = 70
    else:
        gap = abs(profile_level - job_level)
        seniority_score = {0: 100, 1: 90, 2: 65, 3: 40}.get(gap, 25)

    prefers_remote = profile.work_mode == "remote" or any(loc.casefold() == "remote" for loc in profile.locations)
    if remote_type == "remote" and prefers_remote:
        location_score = 100
    elif remote_type == "remote" and not prefers_remote:
        location_score = 85
    elif country and country.casefold() in {loc.casefold() for loc in profile.locations}:
        location_score = 90
    elif location and any(loc.casefold() in location.casefold() for loc in profile.locations if len(loc) > 2):
        location_score = 85
    elif not location and not country:
        location_score = 60
    else:
        location_score = 50

    salary_score = 50  # neutral: salary data is rarely reliable enough to score.

    resume_norm = _norm(resume_text)
    profile_terms = profile_skills | {_norm(r) for r in profile.roles}
    job_terms = set(job_text.split())
    if resume_norm:
        overlap = profile_terms & job_terms
        responsibility_score = _clamp(100 * min(1.0, len(overlap) / 10))
    else:
        responsibility_score = 55

    overall = _clamp(
        0.45 * skill_score
        + 0.20 * experience_score
        + 0.10 * seniority_score
        + 0.10 * location_score
        + 0.05 * salary_score
        + 0.10 * responsibility_score
    )

    if overall >= 80:
        recommendation = "Strong Match"
    elif overall >= 65:
        recommendation = "Good Match"
    elif overall >= 50:
        recommendation = "Possible Match"
    else:
        recommendation = "Weak Match"

    related = sorted({s for s in job_skills if s in profile_terms or s in resume_norm} - set(matched))[:6]

    return MatchResult(
        overall_score=overall,
        skill_score=skill_score,
        experience_score=experience_score,
        seniority_score=seniority_score,
        location_score=location_score,
        salary_score=salary_score,
        responsibility_score=responsibility_score,
        matched_skills=matched,
        missing_skills=missing,
        critical_missing=critical_missing,
        related_skills=related,
        recommendation=recommendation,
    )
