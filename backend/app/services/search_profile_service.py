"""Build a structured SearchProfile from the user's resume + profile data.

Only evidence present on the resume / profile is used. Skills are never invented and
roles are only expanded from the resume designation (with conservative synonyms).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.profile import Profile
from app.db.models.resume import Resume
from app.db.models.skill import Skill
from app.db.models.user import User, user_skills
from app.services.job_enrichment_service import classify_seniority, infer_country

logger = logging.getLogger(__name__)

ROLE_SYNONYMS: dict[str, list[str]] = {
    "backend": ["Backend Developer", "Backend Engineer", "Backend Software Engineer", "Full Stack Developer"],
    "frontend": ["Frontend Developer", "Frontend Engineer", "Full Stack Developer"],
    "full stack": ["Full Stack Developer", "Full Stack Engineer"],
    "fullstack": ["Full Stack Developer", "Full Stack Engineer"],
    "data scientist": ["Data Scientist", "Machine Learning Engineer", "Data Analyst", "Data Engineer"],
    "data engineer": ["Data Engineer", "Data Analyst", "Data Scientist"],
    "machine learning": ["Machine Learning Engineer", "AI Engineer", "Applied Scientist"],
    "ml": ["Machine Learning Engineer", "AI Engineer"],
    "ai": ["AI Engineer", "Machine Learning Engineer"],
    "android": ["Android Developer", "Android Engineer", "Mobile Developer"],
    "ios": ["iOS Developer", "iOS Engineer", "Mobile Developer"],
    "mobile": ["Mobile Developer", "Android Developer", "iOS Developer"],
    "devops": ["DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer"],
    "sre": ["Site Reliability Engineer", "DevOps Engineer"],
    "qa": ["QA Engineer", "SDET", "Software Tester"],
    "test": ["QA Engineer", "Software Tester"],
    "product manager": ["Product Manager", "Product Owner"],
    "ux": ["UX Designer", "Product Designer", "UI Designer"],
    "designer": ["Designer", "Product Designer", "UX Designer"],
    "analyst": ["Data Analyst", "Business Analyst"],
    "sales": ["Sales Development Representative", "Account Executive", "Sales Representative"],
    "marketing": ["Marketing Manager", "Growth Marketing"],
    "dev": ["Software Developer", "Software Engineer"],
    "software engineer": ["Software Engineer", "Software Developer"],
    "developer": ["Software Developer", "Software Engineer"],
}


@dataclass
class SearchProfile:
    roles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    experience_years: float | None = None
    locations: list[str] = field(default_factory=list)
    seniority: str | None = None
    work_mode: str | None = None
    designation: str | None = None

    def to_dict(self) -> dict:
        return {
            "roles": self.roles,
            "skills": self.skills,
            "experienceYears": self.experience_years,
            "locations": self.locations,
            "seniority": self.seniority,
            "workMode": self.work_mode,
            "designation": self.designation,
        }


def parse_resume_payload(resume: Resume) -> dict:
    if not resume or not resume.parsed_data:
        return {}
    try:
        data = json.loads(resume.parsed_data)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def expand_roles(designation: str, skills: list[str]) -> list[str]:
    """Expand a designation into related role titles using only evidence from the resume."""
    des = (designation or "").strip()
    roles: list[str] = []
    if des:
        roles.append(des)
        low = des.lower()
        for keyword, variants in ROLE_SYNONYMS.items():
            if keyword in low:
                for variant in variants:
                    if variant.lower() != low and variant not in roles:
                        roles.append(variant)
    # "Node.js Developer" style roles from skill + role noun.
    tail = None
    for noun in ("developer", "engineer", "scientist", "designer", "manager", "architect"):
        if re.search(rf"\b{noun}\b", des.lower()):
            tail = noun.title()
            break
    if tail:
        for skill in skills[:3]:
            title = f"{skill} {tail}"
            if title.lower() not in {r.lower() for r in roles}:
                roles.append(title)
    return roles[:10]


def infer_experience_years(experience: list) -> float | None:
    """Estimate years of experience from date ranges in the experience section."""
    best: float | None = None
    for entry in experience:
        text = str(entry or "")
        years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", text)]
        if not years:
            continue
        start = min(years)
        end = 2026 if "present" in text.lower() or "current" in text.lower() else max(years)
        span = max(0.0, end - start + 1)
        if best is None or span > best:
            best = span
    return min(best, 40.0) if best is not None else None


async def build_search_profile(db: AsyncSession, user: User) -> SearchProfile | None:
    """Build a SearchProfile from the user's latest resume. None when no resume exists."""
    resume_result = await db.execute(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        return None
    payload = parse_resume_payload(resume)

    designation = str(payload.get("designation") or "").strip() or None
    skills = [str(s).strip() for s in (payload.get("skills") or []) if str(s).strip()]
    experience = payload.get("experience") or []

    # User-stated skills (evidence from their account) merged with resume skills.
    user_skill_result = await db.execute(
        select(Skill.name).join(user_skills, user_skills.c.skill_id == Skill.id).where(user_skills.c.user_id == user.id)
    )
    for (name,) in user_skill_result.all():
        name = str(name).strip()
        if name and name.lower() not in {s.lower() for s in skills}:
            skills.append(name)
    skills = skills[:25]

    profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    profile_location = (profile.location if profile else None) or ""

    locations: list[str] = []
    if profile_location:
        locations.append(profile_location)
    country = infer_country(profile_location)
    if country and country != "Remote":
        locations.append(country)
    work_mode = None
    low_loc = profile_location.lower()
    if "remote" in low_loc:
        work_mode = "remote"
        locations.append("Remote")
    elif "hybrid" in low_loc:
        work_mode = "hybrid"
        locations.append("Remote")

    return SearchProfile(
        roles=expand_roles(designation or "", skills) if designation else [],
        skills=skills,
        experience_years=infer_experience_years(experience),
        locations=list(dict.fromkeys(locations))[:3],
        seniority=classify_seniority(designation) if designation else None,
        work_mode=work_mode,
        designation=designation,
    )
