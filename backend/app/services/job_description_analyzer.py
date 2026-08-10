"""JobDescriptionAnalyzer: deterministic requirement extraction from job postings.

Extracts skill + experience + education requirements, classifies importance
(REQUIRED / PREFERRED / NICE_TO_HAVE / UNKNOWN) from the posting's own wording, and
flags critical requirements. No LLM involved at ingest time.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.career import JobRequirement, RequirementImportance
from app.db.models.job import Job
from app.services.job_enrichment_service import SKILL_ALIASES, extract_skills
from app.services.job_match_service import CORE_TECH_SKILLS

logger = logging.getLogger(__name__)

_REQUIRED_MARKERS = re.compile(
    r"\b(required|must\b|must have|essential|mandatory|minimum|needs?\b|you will|"
    r"you'll|we expect|solid (knowledge|understanding|experience|proficiency)|"
    r"expertise in|experience with|proficiency in|knowledge of|strong (knowledge|background|experience)|"
    r"hands-on|working knowledge|deep understanding|responsibilities include|core)\b",
    re.IGNORECASE,
)
_PREFERRED_MARKERS = re.compile(
    r"\b(preferred|nice[ -]to[ -]have|bonus|plus|desirable|good to have|"
    r"familiarity with|advantage|beneficial|a plus|is a plus)\b",
    re.IGNORECASE,
)
_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:years|yrs)(?: of)? (?:of )?(?:experience|work)?", re.IGNORECASE)
_DEGREE_RE = re.compile(
    r"\b(bachelor's|bachelors|b\.?s\.?|master's|masters|m\.?s\.?|mba|ph\.?d\.?|phd|"
    r"doctorate|degree|undergraduate|graduate)\b",
    re.IGNORECASE,
)

MAX_REQUIREMENTS = 40


@dataclass
class RequirementData:
    requirement: str
    skill: str | None
    importance: str
    is_critical: bool
    source: str


def _sentences(*texts: str | None) -> list[str]:
    out: list[str] = []
    for text in texts:
        if not text:
            continue
        for part in re.split(r"(?<=[.!?])\s+", text):
            part = " ".join(part.split())
            if part:
                out.append(part)
    return out


def _importance(sentence: str, in_title: bool = False) -> str:
    if in_title or _REQUIRED_MARKERS.search(sentence):
        return RequirementImportance.REQUIRED.value
    if _PREFERRED_MARKERS.search(sentence):
        return RequirementImportance.PREFERRED.value
    return RequirementImportance.NICE_TO_HAVE.value


def _critical(sentence: str, canonical: str | None, importance: str) -> bool:
    if importance != RequirementImportance.REQUIRED.value:
        return False
    if canonical and canonical in CORE_TECH_SKILLS:
        return True
    return bool(re.search(r"\d\s*\+?\s*(?:years|yrs)|\bmust\b|\bcritical\b|\bessential\b", sentence, re.IGNORECASE))


def _sentence_containing(canonical: str, sentences: list[str]) -> str | None:
    aliases = SKILL_ALIASES.get(canonical, [canonical])
    for sentence in sentences:
        lowered = sentence.lower()
        if any(re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", lowered) for a in aliases):
            return sentence
    return None


def _skill_text_contains(skill: str, sentence: str | None) -> bool:
    if not sentence:
        return False
    aliases = SKILL_ALIASES.get(skill, [skill])
    lowered = sentence.lower()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", lowered) for a in aliases)


async def analyze_job_requirements(db: AsyncSession, job: Job) -> list[JobRequirement]:
    """Deterministically extract requirements from a job. Returns the new rows."""
    combined = " ".join(filter(None, [job.title, job.description or "", job.requirements or ""]))
    responsibilities = job.responsibilities or ""
    sentences = _sentences(job.title, job.description, job.requirements, responsibilities)

    reqs: list[RequirementData] = []
    seen: set[tuple[str, str]] = set()

    for canonical in extract_skills(combined)[:MAX_REQUIREMENTS]:
        if not canonical:
            continue
        key = ("skill", canonical)
        if key in seen:
            continue
        seen.add(key)
        sentence = _sentence_containing(canonical, sentences) or combined
        in_title = _skill_text_contains(canonical, job.title)
        importance = _importance(sentence, in_title=in_title)
        reqs.append(
            RequirementData(
                requirement=canonical,
                skill=canonical,
                importance=importance,
                is_critical=_critical(sentence, canonical, importance),
                source="title" if in_title else "description",
            )
        )

    if job.experience_min is not None or job.experience_max is not None:
        requirement_text = "years of experience"
        sentence = sentences[0] if sentences else combined
        reqs.append(
            RequirementData(
                requirement=requirement_text,
                skill=None,
                importance=RequirementImportance.REQUIRED.value if "senior" in (job.title or "").lower()
                else RequirementImportance.PREFERRED.value,
                is_critical=False,
                source="posting",
            )
        )

    text_lower = combined.lower()
    for match in re.finditer(_YEARS_RE, text_lower):
        text = match.group(0).strip()
        if ("skill", "years") in seen or any(r.requirement == text for r in reqs):
            continue
        seen.add(("skill", "years"))
        reqs.append(
            RequirementData(
                requirement=text,
                skill=None,
                importance=RequirementImportance.REQUIRED.value,
                is_critical=False,
                source="description",
            )
        )

    if _DEGREE_RE.search(text_lower):
        reqs.append(
            RequirementData(
                requirement="degree",
                skill=None,
                importance=RequirementImportance.PREFERRED.value,
                is_critical=False,
                source="description",
            )
        )

    order = {RequirementImportance.REQUIRED.value: 0, RequirementImportance.PREFERRED.value: 1,
             RequirementImportance.NICE_TO_HAVE.value: 2, RequirementImportance.UNKNOWN.value: 3}
    reqs.sort(key=lambda r: (order[r.importance], r.requirement))

    from sqlalchemy import delete as sa_delete

    await db.execute(sa_delete(JobRequirement).where(JobRequirement.job_id == job.id))
    await db.flush()

    rows: list[JobRequirement] = []
    for data in reqs[:MAX_REQUIREMENTS]:
        row = JobRequirement(
            job_id=job.id,
            requirement=data.requirement,
            skill=data.skill,
            importance=data.importance,
            is_critical=data.is_critical,
            source=data.source,
        )
        db.add(row)
        rows.append(row)
    return rows


async def get_job_requirements(db: AsyncSession, job: Job) -> list[JobRequirement]:
    rows = (
        (await db.execute(select(JobRequirement).where(JobRequirement.job_id == job.id)))
        .scalars()
        .all()
    )
    if not rows:
        rows = await analyze_job_requirements(db, job)
        await db.commit()
    return list(rows)
