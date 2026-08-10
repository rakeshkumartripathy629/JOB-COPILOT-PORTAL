"""Career Vault: user career facts + evidence.

Facts are extracted deterministically from the parsed resume and the user's stated
skills. Nothing is invented: every fact carries at least one piece of evidence.
Rebuilding is idempotent and preserves facts the user explicitly verified/confirmed
or rejected.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.career import (
    CareerEvidence,
    CareerFact,
    CareerFactStatus,
    CareerFactType,
    EvidenceType,
)
from app.db.models.resume import Resume
from app.db.models.skill import Skill
from app.db.models.user import user_skills
from app.services.search_profile_service import parse_resume_payload
from app.services.skill_classifier import STATUS_CONFIDENCE, skill_fact_type

logger = logging.getLogger(__name__)

_AUTO_STATUSES = {CareerFactStatus.AI_EXTRACTED.value, CareerFactStatus.INFERRED.value}

_PROJECT_VERBS = re.compile(
    r"\b(built|developed|designed|created|implemented|migrated|architected|engineered|"
    r"constructed|deployed|shipped|launched|delivered)\b",
    re.IGNORECASE,
)
_ACHIEVEMENT_VERBS = re.compile(
    r"\b(improved|increased|reduced|boosted|achieved|optimized|streamlined|grew|saved|"
    r"cut|earned|won|led|scaled|accelerated|drove|automated|doubled|tripled)\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_QUANT_RE = re.compile(r"\b(\d+%|percent|)\b|\d+")


def _short(value: str, limit: int = 100) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _split_sentences(text: str) -> list[str]:
    parts = [_short(s, limit=280) for s in _SENTENCE_RE.split(text)]
    return [p for p in parts if len(p) > 20]


async def _latest_resume(db: AsyncSession, user_id: int) -> Resume | None:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _existing_facts(db: AsyncSession, user_id: int) -> dict[tuple[str, str], CareerFact]:
    rows = (
        (
            await db.execute(
                select(CareerFact).options(selectinload(CareerFact.evidence)).where(CareerFact.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    return {(f.fact_type, f.name.lower()): f for f in rows}


async def rebuild_career_vault(db: AsyncSession, user_id: int) -> dict:
    """(Re)build career facts + evidence from the latest resume. Idempotent."""
    resume = await _latest_resume(db, user_id)
    if resume is None:
        raise ValueError("Upload a resume to build your career evidence.")
    payload = parse_resume_payload(resume)

    existing = await _existing_facts(db, user_id)

    await db.execute(
        delete(CareerFact).where(
            CareerFact.user_id == user_id,
            CareerFact.status.in_(_AUTO_STATUSES),
        )
    )
    await db.execute(
        delete(CareerEvidence).where(CareerEvidence.user_id == user_id, CareerEvidence.source == "resume")
    )
    await db.flush()

    created = 0
    kept = 0

    def add_fact(
        fact_type: str,
        name: str,
        *,
        value: str | None = None,
        description: str | None = None,
        confidence: int = 80,
        status: str = CareerFactStatus.AI_EXTRACTED.value,
    ) -> CareerFact | None:
        nonlocal created, kept
        name = " ".join((name or "").split())
        if not name:
            return None
        key = (fact_type, name.lower())
        existing_fact = existing.get(key)
        if existing_fact:
            if existing_fact.status == CareerFactStatus.REJECTED.value:
                return None
            existing_fact.value = value
            existing_fact.description = description
            existing_fact.confidence = confidence
            existing_fact.status = status
            kept += 1
            return existing_fact
        fact = CareerFact(
            user_id=user_id,
            fact_type=fact_type,
            name=name,
            value=value,
            description=description,
            confidence=confidence,
            status=status,
            verified_by_user=False,
            is_public=True,
        )
        db.add(fact)
        created += 1
        return fact

    def add_evidence(
        fact: CareerFact,
        *,
        evidence_type: str,
        source: str,
        source_id: int | None,
        source_section: str,
        evidence_text: str,
        confidence: int,
        verification_status: str = CareerFactStatus.AI_EXTRACTED.value,
    ) -> None:
        fact.evidence.append(
            CareerEvidence(
                user_id=user_id,
                evidence_type=evidence_type,
                source=source,
                source_id=source_id,
                source_section=source_section,
                evidence_text=evidence_text,
                confidence=confidence,
                verification_status=verification_status,
                verified_by_user=False,
            )
        )

    skills = [str(s).strip() for s in (payload.get("skills") or []) if str(s).strip()]
    for skill in skills[:50]:
        fact = add_fact(skill_fact_type(skill), skill, value=skill, confidence=80)
        if fact:
            add_evidence(
                fact,
                evidence_type=EvidenceType.RESUME_SECTION.value,
                source="resume",
                source_id=resume.id,
                source_section="skills",
                evidence_text=skill,
                confidence=80,
            )

    designation = str(payload.get("designation") or "").strip()
    if designation:
        fact = add_fact(
            CareerFactType.JOB_TITLE.value,
            designation,
            value=designation,
            description="Current role from resume",
            confidence=85,
        )
        if fact:
            add_evidence(
                fact,
                evidence_type=EvidenceType.RESUME_SECTION.value,
                source="resume",
                source_id=resume.id,
                source_section="designation",
                evidence_text=designation,
                confidence=85,
            )

    for entry in (payload.get("experience") or []):
        text = str(entry or "").strip()
        if not text:
            continue
        fact = add_fact(
            CareerFactType.EXPERIENCE.value,
            _short(text.split("\n")[0]),
            value=text,
            confidence=75,
        )
        if fact:
            add_evidence(
                fact,
                evidence_type=EvidenceType.RESUME_EXPERIENCE.value,
                source="resume",
                source_id=resume.id,
                source_section="experience",
                evidence_text=text,
                confidence=75,
            )
        for sentence in _split_sentences(text):
            if _ACHIEVEMENT_VERBS.search(sentence):
                ach = add_fact(
                    CareerFactType.ACHIEVEMENT.value,
                    _short(sentence, limit=90),
                    value=sentence,
                    confidence=60,
                    status=CareerFactStatus.INFERRED.value,
                )
                if ach:
                    add_evidence(
                        ach,
                        evidence_type=EvidenceType.RESUME_ACHIEVEMENT.value,
                        source="resume",
                        source_id=resume.id,
                        source_section="experience",
                        evidence_text=sentence,
                        confidence=60,
                        verification_status=CareerFactStatus.INFERRED.value,
                    )
            elif _PROJECT_VERBS.search(sentence):
                proj = add_fact(
                    CareerFactType.PROJECT.value,
                    _short(sentence, limit=90),
                    value=sentence,
                    confidence=60,
                    status=CareerFactStatus.INFERRED.value,
                )
                if proj:
                    add_evidence(
                        proj,
                        evidence_type=EvidenceType.RESUME_PROJECT.value,
                        source="resume",
                        source_id=resume.id,
                        source_section="experience",
                        evidence_text=sentence,
                        confidence=60,
                        verification_status=CareerFactStatus.INFERRED.value,
                    )

    for entry in (payload.get("education") or []):
        text = str(entry or "").strip()
        if not text:
            continue
        fact = add_fact(CareerFactType.EDUCATION.value, _short(text), value=text, confidence=80)
        if fact:
            add_evidence(
                fact,
                evidence_type=EvidenceType.RESUME_EDUCATION.value,
                source="resume",
                source_id=resume.id,
                source_section="education",
                evidence_text=text,
                confidence=80,
            )

    for entry in (payload.get("certifications") or []):
        text = str(entry or "").strip()
        if not text:
            continue
        fact = add_fact(CareerFactType.CERTIFICATION.value, _short(text), value=text, confidence=80)
        if fact:
            add_evidence(
                fact,
                evidence_type=EvidenceType.RESUME_CERTIFICATION.value,
                source="resume",
                source_id=resume.id,
                source_section="certifications",
                evidence_text=text,
                confidence=80,
            )

    user_skill_rows = await db.execute(
        select(Skill.name, user_skills.c.proficiency_level, user_skills.c.years_experience)
        .join(user_skills, user_skills.c.skill_id == Skill.id)
        .where(user_skills.c.user_id == user_id)
    )
    for name, proficiency, years in user_skill_rows.all():
        name = str(name or "").strip()
        if not name:
            continue
        fact = add_fact(
            skill_fact_type(name),
            name,
            value=proficiency or "Known",
            description=f"User-stated skill ({years} yrs)" if years else "User-stated skill",
            confidence=90,
            status=CareerFactStatus.USER_CONFIRMED.value,
        )
        if fact:
            add_evidence(
                fact,
                evidence_type=EvidenceType.USER_SKILLS.value,
                source="user",
                source_id=user_id,
                source_section="profile",
                evidence_text=f"{name}" + (f" ({years} years)" if years else ""),
                confidence=90,
                verification_status=CareerFactStatus.USER_CONFIRMED.value,
            )

    await db.commit()
    logger.info("career vault rebuilt for user %s: %d created, %d kept", user_id, created, kept)
    return {"facts_created": created, "facts_kept": kept}


async def ensure_career_vault(db: AsyncSession, user_id: int) -> bool:
    """Build the vault on demand when the user has no facts yet. True if built."""
    has = (
        await db.execute(select(CareerFact.id).where(CareerFact.user_id == user_id).limit(1))
    ).scalar_one_or_none()
    if has:
        return False
    try:
        await rebuild_career_vault(db, user_id)
    except ValueError:
        return False
    return True


async def get_career_facts(
    db: AsyncSession,
    user_id: int,
    *,
    status: str | None = None,
    fact_type: str | None = None,
    limit: int = 500,
) -> list[CareerFact]:
    query = select(CareerFact).where(CareerFact.user_id == user_id)
    if status:
        query = query.where(CareerFact.status == status)
    if fact_type:
        query = query.where(CareerFact.fact_type == fact_type)
    query = query.order_by(CareerFact.updated_at.desc()).limit(min(limit, 1000))
    return list((await db.execute(query)).scalars().all())


async def get_career_evidence(
    db: AsyncSession,
    user_id: int,
    *,
    fact_id: int | None = None,
    limit: int = 500,
) -> list[CareerEvidence]:
    query = select(CareerEvidence).where(CareerEvidence.user_id == user_id)
    if fact_id:
        query = query.where(CareerEvidence.career_fact_id == fact_id)
    query = query.order_by(CareerEvidence.updated_at.desc()).limit(min(limit, 1000))
    return list((await db.execute(query)).scalars().all())


async def update_career_fact(
    db: AsyncSession,
    user_id: int,
    fact_id: int,
    *,
    status: str | None = None,
    name: str | None = None,
    value: str | None = None,
    description: str | None = None,
    confidence: int | None = None,
    is_public: bool | None = None,
) -> CareerFact | None:
    fact = (
        await db.execute(
            select(CareerFact).where(CareerFact.id == fact_id, CareerFact.user_id == user_id)
        )
    ).scalar_one_or_none()
    if fact is None:
        return None
    valid_statuses = {s.value for s in CareerFactStatus}
    if status is not None:
        if status not in valid_statuses:
            raise ValueError(f"status must be one of {sorted(valid_statuses)}")
        fact.status = status
    if name is not None:
        fact.name = name
    if value is not None:
        fact.value = value
    if description is not None:
        fact.description = description
    if confidence is not None:
        fact.confidence = max(0, min(100, int(confidence)))
    if is_public is not None:
        fact.is_public = is_public
    if fact.status in {CareerFactStatus.VERIFIED.value, CareerFactStatus.USER_CONFIRMED.value,
                       CareerFactStatus.REJECTED.value}:
        fact.verified_by_user = True
        fact.confidence = STATUS_CONFIDENCE[fact.status]
    await db.commit()
    await db.refresh(fact)
    return fact


async def update_career_evidence(
    db: AsyncSession,
    user_id: int,
    evidence_id: int,
    *,
    verification_status: str | None = None,
) -> CareerEvidence | None:
    evidence = (
        await db.execute(
            select(CareerEvidence).where(CareerEvidence.id == evidence_id, CareerEvidence.user_id == user_id)
        )
    ).scalar_one_or_none()
    if evidence is None:
        return None
    if verification_status is not None:
        valid_statuses = {s.value for s in CareerFactStatus}
        if verification_status not in valid_statuses:
            raise ValueError(f"verification_status must be one of {sorted(valid_statuses)}")
        evidence.verification_status = verification_status
        if verification_status in {CareerFactStatus.VERIFIED.value, CareerFactStatus.USER_CONFIRMED.value,
                                   CareerFactStatus.REJECTED.value}:
            evidence.verified_by_user = True
        evidence.confidence = STATUS_CONFIDENCE[verification_status]
    await db.commit()
    await db.refresh(evidence)
    return evidence


async def get_resume_facts(db: AsyncSession, user_id: int) -> list[CareerFact]:
    """All active (non-REJECTED) facts used by the matching engine."""
    rows = (
        (
            await db.execute(
                select(CareerFact)
                .options(selectinload(CareerFact.evidence))
                .where(CareerFact.user_id == user_id, CareerFact.status != CareerFactStatus.REJECTED.value)
                .order_by(CareerFact.confidence.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)
