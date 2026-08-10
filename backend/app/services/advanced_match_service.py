"""Advanced resume-to-job matching with evidence.

Improves the existing deterministic `match_job` by adding an evidence layer:
requirements are classified against the user's Career Vault facts, producing a
requirement matrix, critical-missing detection, match confidence, relevant projects/
achievements/experience, and human-readable why/why-not explanations.

All scores stay within 0-100. Requirement classification is strict: a related skill is
never a direct match and never satisfies a critical requirement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.career import (
    CareerFact,
    CareerFactType,
    JobMatchEvidence,
    JobRequirementMatch,
)
from app.db.models.job import Job
from app.services.job_description_analyzer import _DEGREE_RE, _YEARS_RE, get_job_requirements
from app.services.job_match_service import _clamp, _norm, match_job
from app.services.search_profile_service import SearchProfile
from app.services.skill_classifier import (
    DIRECT_MATCH,
    NO_EVIDENCE,
    PARTIAL_MATCH,
    RELATED_MATCH,
    STATUS_CONFIDENCE,
    _partial_overlap,
    classify_requirement,
)

logger = logging.getLogger(__name__)

SKILL_FACT_TYPES = {
    CareerFactType.TECHNICAL_SKILL.value,
    CareerFactType.SOFT_SKILL.value,
    CareerFactType.TOOL.value,
}
TEXT_FACT_TYPES = {
    CareerFactType.PROJECT.value,
    CareerFactType.ACHIEVEMENT.value,
    CareerFactType.EXPERIENCE.value,
    CareerFactType.RESPONSIBILITY.value,
    CareerFactType.JOB_TITLE.value,
}


@dataclass
class AdvancedMatch:
    overall_score: int
    required_skill_score: int
    preferred_skill_score: int
    education_score: int
    career_goal_score: int
    experience_score: int
    seniority_score: int
    location_score: int
    salary_score: int
    responsibility_score: int
    match_confidence: int
    recommendation: str
    requirements: list[dict] = field(default_factory=list)
    critical_missing: list[str] = field(default_factory=list)
    matched_facts: list[dict] = field(default_factory=list)
    relevant_projects: list[str] = field(default_factory=list)
    relevant_achievements: list[str] = field(default_factory=list)
    relevant_experience: list[str] = field(default_factory=list)
    why_match: str = ""
    why_not: str = ""
    match_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "required_skill_score": self.required_skill_score,
            "preferred_skill_score": self.preferred_skill_score,
            "education_score": self.education_score,
            "career_goal_score": self.career_goal_score,
            "experience_score": self.experience_score,
            "seniority_score": self.seniority_score,
            "location_score": self.location_score,
            "salary_score": self.salary_score,
            "responsibility_score": self.responsibility_score,
            "match_confidence": self.match_confidence,
            "recommendation": self.recommendation,
            "requirements": self.requirements,
            "critical_missing": self.critical_missing,
            "matched_facts": self.matched_facts,
            "relevant_projects": self.relevant_projects,
            "relevant_achievements": self.relevant_achievements,
            "relevant_experience": self.relevant_experience,
            "why_match": self.why_match,
            "why_not": self.why_not,
            "match_reason": self.match_reason,
        }

    def requirement_counts(self) -> dict:
        counts: dict[str, Any] = {"met": 0, "related": 0, "partial": 0, "missing": 0}
        for req in self.requirements:
            cls = req.get("classification")
            if cls == DIRECT_MATCH:
                counts["met"] += 1
            elif cls == RELATED_MATCH:
                counts["related"] += 1
            elif cls == PARTIAL_MATCH:
                counts["partial"] += 1
            else:
                counts["missing"] += 1
        counts["critical_missing"] = self.critical_missing
        return counts


def _education_match(facts: list[CareerFact]) -> tuple[str, CareerFact | None, int]:
    edu = [f for f in facts if f.fact_type == CareerFactType.EDUCATION.value]
    if edu:
        return DIRECT_MATCH, edu[0], 100
    return NO_EVIDENCE, None, 0


def _years_required(requirement_text: str) -> int | None:
    match = re.search(r"(\d+)", requirement_text)
    return int(match.group(1)) if match else None


def _experience_text_match(
    requirement_text: str, years: float | None
) -> tuple[str, CareerFact | None, int]:
    required = _years_required(requirement_text)
    if required is None:
        return NO_EVIDENCE, None, 0
    if years is None:
        return NO_EVIDENCE, None, 20
    if years >= required:
        return DIRECT_MATCH, None, 100
    if years >= required - 1:
        return PARTIAL_MATCH, None, 60
    return NO_EVIDENCE, None, 15


def _career_goal_score(title: str, roles: list[str]) -> int:
    title_low = _norm(title)
    for role in roles:
        if _norm(role) and _norm(role) in title_low:
            return 100
    title_tokens = set(title_low.split())
    role_tokens: set[str] = set()
    for role in roles:
        role_tokens |= set(_norm(role).split())
    overlap = title_tokens & role_tokens
    if overlap:
        return _clamp(70 + 10 * len(overlap))
    return 50


def _fact_confidence(fact: CareerFact | None) -> int:
    if fact is None:
        return 0
    return STATUS_CONFIDENCE.get(fact.status, 30)


def _best_evidence(fact: CareerFact) -> str:
    if fact.evidence:
        ordered = sorted(fact.evidence, key=lambda e: e.confidence, reverse=True)
        return ordered[0].evidence_text or fact.value or fact.name
    return fact.value or fact.name


async def compute_advanced_match(
    db: AsyncSession,
    *,
    user_id: int,
    job: Job,
    profile: SearchProfile,
    facts: list[CareerFact],
    resume_text: str = "",
) -> AdvancedMatch:
    requirements = await get_job_requirements(db, job)
    skills_facts = [f for f in facts if f.fact_type in SKILL_FACT_TYPES]
    text_facts = [f for f in facts if f.fact_type in TEXT_FACT_TYPES]
    profile_skills = [f.name for f in skills_facts if f.name]

    base = match_job(
        profile=profile,
        title=job.title,
        description=job.description,
        requirements=job.requirements,
        skills=(job.skills_required.split(",") if job.skills_required else None),
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        seniority=job.seniority,
        location=job.location,
        country=job.country,
        remote_type=job.remote_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        resume_text=resume_text,
    )

    required_scores: list[int] = []
    preferred_scores: list[int] = []
    matrix: list[dict] = []
    critical_missing: list[str] = []
    matched_facts_map: dict[int, dict] = {}
    matched_skills: list[str] = []

    for req in requirements:
        classification: str = NO_EVIDENCE
        matched_fact: CareerFact | None = None
        score = 0
        evidence_text: str | None = None

        if req.skill:
            classification, profile_skill, score = classify_requirement(req.requirement, profile_skills)
            if profile_skill:
                key = profile_skill.strip().lower()
                for f in skills_facts:
                    if f.name.strip().lower() == key:
                        matched_fact = f
                        break
                evidence_text = _best_evidence(matched_fact) if matched_fact else profile_skill
        elif req.requirement in ("years of experience",):
            if job.experience_min is not None and profile.experience_years is not None:
                if profile.experience_years >= job.experience_min:
                    classification, score = DIRECT_MATCH, 100
                elif profile.experience_years >= job.experience_min - 1:
                    classification, score = PARTIAL_MATCH, 60
                else:
                    classification, score = NO_EVIDENCE, 20
            elif profile.experience_years is None:
                classification, score = NO_EVIDENCE, 30
            else:
                classification, score = DIRECT_MATCH, 80
            if score >= 80:
                matched_skills.append(f"{profile.experience_years:.0f}+ yrs experience")
        elif req.requirement == "degree":
            classification, matched_fact, score = _education_match(facts)
            evidence_text = _best_evidence(matched_fact) if matched_fact else None
        elif _YEARS_RE.search(req.requirement):
            classification, matched_fact, score = _experience_text_match(req.requirement, profile.experience_years)
            evidence_text = _best_evidence(matched_fact) if matched_fact else None
        else:
            for f in text_facts:
                if _partial_overlap(req.requirement, f.value or f.name):
                    classification, matched_fact, score = PARTIAL_MATCH, f, 60
                    evidence_text = _best_evidence(f)
                    break
            if matched_fact is None and _DEGREE_RE.search(req.requirement):
                classification, matched_fact, score = _education_match(facts)
                evidence_text = _best_evidence(matched_fact) if matched_fact else None

        if req.importance in ("REQUIRED", "PREFERRED") and req.skill:
            target = required_scores if req.importance == "REQUIRED" else preferred_scores
            target.append(score)
        if classification == DIRECT_MATCH and matched_fact is not None:
            matched_facts_map[matched_fact.id] = {
                "fact_id": matched_fact.id,
                "fact_name": matched_fact.name,
                "fact_type": matched_fact.fact_type,
                "classification": classification,
                "evidence_text": evidence_text,
                "confidence": _fact_confidence(matched_fact),
            }
        if classification == DIRECT_MATCH and req.skill:
            matched_skills.append(req.requirement)

        if req.importance == "REQUIRED" and req.is_critical and classification != DIRECT_MATCH:
            critical_missing.append(req.requirement)

        matrix.append(
            {
                "requirement_id": req.id,
                "requirement": req.requirement,
                "skill": req.skill,
                "importance": req.importance,
                "is_critical": bool(req.is_critical),
                "classification": classification,
                "fact_id": matched_fact.id if matched_fact else None,
                "fact_name": matched_fact.name if matched_fact else None,
                "skill_score": score,
                "confidence": _fact_confidence(matched_fact) if matched_fact else (100 if score == 100 else 0),
                "evidence_text": evidence_text,
            }
        )

    required_skill_score = _clamp(sum(required_scores) / len(required_scores)) if required_scores else 60
    preferred_skill_score = _clamp(sum(preferred_scores) / len(preferred_scores)) if preferred_scores else 50

    has_education_req = any(m["skill"] is None and m["requirement"] == "degree" for m in matrix)
    edu_classification, edu_fact, _edu_score = _education_match(facts)
    education_score = 100 if (edu_fact and has_education_req) else (60 if not has_education_req else 25)

    career_goal_score = _career_goal_score(job.title, profile.roles)

    overall = _clamp(
        0.45 * required_skill_score
        + 0.10 * preferred_skill_score
        + 0.15 * base.experience_score
        + 0.08 * base.seniority_score
        + 0.05 * education_score
        + 0.05 * career_goal_score
        + 0.07 * base.location_score
        + 0.05 * base.responsibility_score
    )

    matched_facts_list = list(matched_facts_map.values())
    matched_conf = (
        _clamp(sum(f["confidence"] for f in matched_facts_list) / len(matched_facts_list))
        if matched_facts_list
        else 50
    )
    match_confidence = _clamp(0.65 * matched_conf + 0.35 * overall)

    recommendation = _recommendation(overall, critical_missing)

    why_match_parts: list[str] = []
    direct = [m["requirement"] for m in matrix if m["classification"] == DIRECT_MATCH and m["skill"]]
    if direct:
        why_match_parts.append("Directly matches: " + ", ".join(direct[:6]))
    if edu_fact and has_education_req:
        why_match_parts.append("Education matches the role.")
    if base.experience_score >= 80:
        why_match_parts.append("Experience fits the required band.")
    if not why_match_parts:
        why_match_parts.append(f"{overall}% overall match based on resume evidence.")

    why_not_parts: list[str] = []
    if critical_missing:
        why_not_parts.append("Missing critical: " + ", ".join(critical_missing[:5]))
    else:
        missing = [m["requirement"] for m in matrix if m["classification"] == NO_EVIDENCE and m["skill"]]
        if missing:
            why_not_parts.append("No evidence for: " + ", ".join(missing[:5]))

    relevant_projects = _relevant_texts(facts, CareerFactType.PROJECT.value, job)
    relevant_achievements = _relevant_texts(facts, CareerFactType.ACHIEVEMENT.value, job)
    relevant_experience = _relevant_texts(facts, CareerFactType.EXPERIENCE.value, job)

    match_reason = " | ".join(
        (["Matched: " + ", ".join(matched_skills[:6])] if matched_skills else [])
        + (["Missing core: " + ", ".join(critical_missing[:4])] if critical_missing else [])
    )
    if not match_reason:
        match_reason = f"{overall}% evidence-based match"

    return AdvancedMatch(
        overall_score=overall,
        required_skill_score=required_skill_score,
        preferred_skill_score=preferred_skill_score,
        education_score=education_score,
        career_goal_score=career_goal_score,
        experience_score=base.experience_score,
        seniority_score=base.seniority_score,
        location_score=base.location_score,
        salary_score=base.salary_score,
        responsibility_score=base.responsibility_score,
        match_confidence=match_confidence,
        recommendation=recommendation,
        requirements=matrix,
        critical_missing=list(dict.fromkeys(critical_missing)),
        matched_facts=matched_facts_list,
        relevant_projects=relevant_projects,
        relevant_achievements=relevant_achievements,
        relevant_experience=relevant_experience,
        why_match=" ".join(why_match_parts),
        why_not=" ".join(why_not_parts) or "No obvious gaps.",
        match_reason=match_reason,
    )


def _recommendation(overall: int, critical_missing: list[str]) -> str:
    if overall >= 80 and not critical_missing:
        return "Strong Match"
    if overall >= 80:
        return "Good Match"
    if overall >= 65:
        return "Good Match"
    if overall >= 50:
        return "Possible Match"
    return "Weak Match"


def _relevant_texts(facts: list[CareerFact], fact_type: str, job: Job) -> list[str]:
    job_text = " ".join(filter(None, [job.title, job.description or "", job.requirements or ""])).lower()
    out: list[str] = []
    for f in facts:
        if f.fact_type != fact_type:
            continue
        value = f.value or f.name
        if not value:
            continue
        tokens = _tokens_of(value)
        if tokens & _tokens_of(job_text) or _partial_overlap(job_text, value):
            out.append(value)
        if len(out) >= 5:
            break
    return out


def _tokens_of(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9+#.]+", text.lower()) if len(t) >= 3}


async def persist_advanced_match(
    db: AsyncSession,
    *,
    user_id: int,
    job: Job,
    match: AdvancedMatch,
) -> dict:
    await db.execute(
        delete(JobRequirementMatch).where(
            JobRequirementMatch.job_id == job.id, JobRequirementMatch.user_id == user_id
        )
    )
    await db.execute(
        delete(JobMatchEvidence).where(
            JobMatchEvidence.job_id == job.id, JobMatchEvidence.user_id == user_id
        )
    )
    await db.flush()

    match_count = 0
    evidence_count = 0
    for item in match.requirements:
        db.add(
            JobRequirementMatch(
                job_id=job.id,
                user_id=user_id,
                requirement_id=item["requirement_id"],
                career_fact_id=item.get("fact_id"),
                fact_name=item.get("fact_name"),
                classification=item["classification"],
                skill_score=item["skill_score"],
                confidence=item.get("confidence", 0),
                evidence_text=item.get("evidence_text"),
            )
        )
        match_count += 1

    for fact in match.matched_facts:
        db.add(
            JobMatchEvidence(
                job_id=job.id,
                user_id=user_id,
                career_fact_id=fact["fact_id"],
                fact_name=fact["fact_name"],
                fact_type=fact["fact_type"],
                classification=fact["classification"],
                reason=None,
                evidence_text=fact["evidence_text"],
                confidence=fact["confidence"],
            )
        )
        evidence_count += 1

    await db.flush()
    return {"requirement_matches": match_count, "evidence_records": evidence_count}


async def compute_and_persist(
    db: AsyncSession,
    *,
    user_id: int,
    job: Job,
    profile: SearchProfile,
    facts: list[CareerFact],
    resume_text: str = "",
) -> AdvancedMatch:
    match = await compute_advanced_match(
        db, user_id=user_id, job=job, profile=profile, facts=facts, resume_text=resume_text
    )
    await persist_advanced_match(db, user_id=user_id, job=job, match=match)
    return match


async def get_persisted_requirement_matches(
    db: AsyncSession, user_id: int, job_id: int
) -> list[JobRequirementMatch]:
    rows = (
        await db.execute(
            select(JobRequirementMatch)
            .where(JobRequirementMatch.job_id == job_id, JobRequirementMatch.user_id == user_id)
            .order_by(JobRequirementMatch.id.asc())
        )
    ).scalars().all()
    return list(rows)


async def get_persisted_evidence(db: AsyncSession, user_id: int, job_id: int) -> list[JobMatchEvidence]:
    rows = (
        await db.execute(
            select(JobMatchEvidence)
            .where(JobMatchEvidence.job_id == job_id, JobMatchEvidence.user_id == user_id)
            .order_by(JobMatchEvidence.id.asc())
        )
    ).scalars().all()
    return list(rows)


def classification_label(value: str) -> str:
    return {
        DIRECT_MATCH: "Direct match",
        RELATED_MATCH: "Related match",
        PARTIAL_MATCH: "Partial match",
        NO_EVIDENCE: "No evidence",
    }.get(value, value)
