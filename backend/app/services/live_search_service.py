"""Resume-driven live job search orchestration.

Pipeline: resume -> SearchProfile -> queries -> live sources -> normalize -> dedupe ->
freshness -> match -> rank -> persisted results.

Rules that keep this honest:
- No resume means NO personalized search and ZERO jobs.
- Every result is grounded in resume evidence (skills from resume / user account).
- Freshness uses real source posting timestamps; nothing is invented.
- Portal availability is observed, not assumed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.db.models.job_search_result import JobSearchResult
from app.db.models.job_source_reference import JobSourceReference
from app.db.models.search_session import SearchQuery, SearchSession, SearchSourceStatus
from app.db.session import AsyncSessionLocal
from app.services.career_evidence_service import ensure_career_vault, get_resume_facts
from app.services.job_canonicalization_service import canonicalize_jobs
from app.services.job_enrichment_service import enrich
from app.services.job_freshness_service import Freshness, classify_freshness, within_time_range
from app.services.job_match_service import match_job
from app.services.job_ranking_service import job_quality_score, rank_score
from app.services.job_sources import registry
from app.services.job_sources.base import NormalizedJob, SourceStatus
from app.services.query_generator import generate_queries
from app.services.search_profile_service import SearchProfile, build_search_profile, parse_resume_payload

logger = logging.getLogger(__name__)

MAX_TOTAL_RESULTS = 150
MAX_EXTERNAL_CALLS = 60

#: Portals with no dedicated source; jobs are only discoverable via Google search.
UNAVAILABLE_PORTALS = {
    "linkedin": ("LinkedIn", "No direct API; LinkedIn jobs surface via Google search."),
    "indeed": ("Indeed", "No direct API; Indeed jobs surface via Google search."),
    "naukri": ("Naukri", "No direct API; Naukri jobs surface via Google search."),
    "wellfound": ("Wellfound", "No direct API; Wellfound jobs surface via Google search."),
}


class NoResumeError(Exception):
    """Raised when a personalized search is requested without a resume."""


def _job_type_from_remote(remote_type: str | None) -> JobType | None:
    if remote_type == "remote":
        return JobType.REMOTE
    if remote_type == "hybrid":
        return JobType.HYBRID
    if remote_type == "onsite":
        return JobType.ONSITE
    return None


def _best_of(jobs: list[NormalizedJob]) -> NormalizedJob:
    """Pick the richest occurrence as the canonical representative."""
    def richness(job: NormalizedJob) -> int:
        score = 0
        if job.description:
            score += 3
        if job.posted_at:
            score += 2
        if job.salary_min:
            score += 2
        if job.location:
            score += 1
        if job.remote_type:
            score += 1
        if job.skills:
            score += 1
        return score
    return max(jobs, key=richness)


async def get_search_profile_for_user(db: AsyncSession, user_id: int) -> SearchProfile | None:
    """Return the user's SearchProfile, or None when they have no resume (gating)."""
    from app.db.models.user import User

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        return None
    return await build_search_profile(db, user)


async def start_search(
    db: AsyncSession,
    *,
    user_id: int,
    time_range: str = "7d",
    remote: str = "any",
    sources: list[str] | None = None,
) -> int:
    """Create a search session and return its id. Raises NoResumeError when gated."""
    from app.db.models.resume import Resume
    from app.db.models.user import User

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NoResumeError("User not found.")
    resume = (
        await db.execute(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not resume:
        raise NoResumeError("Upload your resume to discover matching jobs.")

    profile = await build_search_profile(db, user)
    if profile is None:
        raise NoResumeError("Upload your resume to discover matching jobs.")

    queries = generate_queries(profile)
    if not queries:
        queries = ["software engineer"]

    available = registry.all()
    available_names = [s.name for s in available]
    requested = [s for s in (sources or available_names) if s in available_names]
    if not requested:
        requested = available_names

    resume_text = _resume_text_for(resume)

    session = SearchSession(
        user_id=user.id,
        resume_id=resume.id,
        status="SEARCHING",
        time_range=time_range,
        remote_filter=remote,
        sources_requested=json.dumps(requested),
        profile_json=json.dumps({**profile.to_dict(), "resumeText": resume_text}, ensure_ascii=False),
        queries_json=json.dumps(queries),
        started_at=datetime.utcnow(),
    )
    db.add(session)
    await db.flush()

    for query in queries:
        db.add(SearchQuery(session_id=session.id, query=query, sources=json.dumps(requested)))

    for name in requested:
        source = registry.get(name)
        db.add(
            SearchSourceStatus(
                session_id=session.id,
                source=name,
                portal=source.display_name if source else name,
                status=SourceStatus.SEARCHING.value,
                count=0,
            )
        )

    for name, (portal, note) in UNAVAILABLE_PORTALS.items():
        if name not in requested and "google_cse" in requested:
            db.add(
                SearchSourceStatus(
                    session_id=session.id,
                    source=name,
                    portal=portal,
                    status=SourceStatus.UNAVAILABLE.value,
                    count=0,
                    error=note,
                )
            )

    await db.commit()
    await db.refresh(session)
    return session.id


def _resume_text_for(resume: Any) -> str:
    try:
        payload = parse_resume_payload(resume)
    except Exception:
        payload = {}
    parts = [
        str(payload.get("summary") or ""),
        " ".join(str(e) for e in (payload.get("experience") or []) if e),
        " ".join(str(e) for e in (payload.get("education") or []) if e),
        " ".join(str(s) for s in (payload.get("skills") or []) if s),
    ]
    return " ".join(p for p in parts if p)[:8000]


async def run_search_task(session_id: int) -> None:
    """Background runner. Uses its own DB session; never raises to the caller."""
    try:
        async with AsyncSessionLocal() as db:
            await _run_search(db, session_id)
    except Exception:
        logger.exception("Live job search session %d failed", session_id)
        try:
            async with AsyncSessionLocal() as db:
                session = (await db.execute(select(SearchSession).where(SearchSession.id == session_id))).scalar_one_or_none()
                if session:
                    session.status = "FAILED"
                    session.error = "Search failed unexpectedly."
                    session.completed_at = datetime.utcnow()
                    await db.commit()
        except Exception:
            logger.exception("Could not mark session %d as failed", session_id)


async def _run_search(db: AsyncSession, session_id: int) -> None:
    session = (await db.execute(select(SearchSession).where(SearchSession.id == session_id))).scalar_one_or_none()
    if not session:
        return

    requested = json.loads(session.sources_requested or "[]")
    queries = json.loads(session.queries_json or '["software engineer"]')
    profile_data = json.loads(session.profile_json or "{}")
    profile = SearchProfile(
        roles=profile_data.get("roles", []),
        skills=profile_data.get("skills", []),
        experience_years=profile_data.get("experienceYears"),
        locations=profile_data.get("locations", []),
        seniority=profile_data.get("seniority"),
        work_mode=profile_data.get("workMode"),
        designation=profile_data.get("designation"),
    )
    resume_text = profile_data.get("resumeText", "")
    remote_filter = (session.remote_filter or "any").lower()
    now = datetime.utcnow()

    career_facts: list[Any] = []
    try:
        await ensure_career_vault(db, session.user_id)
        career_facts = await get_resume_facts(db, session.user_id)
    except Exception:
        logger.exception("career vault setup failed for user %s", session.user_id)

    collected: list[NormalizedJob] = []
    external_calls = 0

    async def _set_status(source: str, status: str, count: int = 0, error: str | None = None) -> None:
        row = (
            await db.execute(
                select(SearchSourceStatus).where(
                    SearchSourceStatus.session_id == session.id, SearchSourceStatus.source == source
                )
            )
        ).scalar_one_or_none()
        if not row:
            row = SearchSourceStatus(
                session_id=session.id,
                source=source,
                portal=source,
                status=status,
                count=count,
                error=error,
            )
            db.add(row)
        row.status = status
        row.count = count
        row.error = error
        row.updated_at = datetime.utcnow()
        await db.commit()

    for query in queries:
        if len(collected) >= MAX_TOTAL_RESULTS or external_calls >= MAX_EXTERNAL_CALLS:
            break
        for source_name in requested:
            if len(collected) >= MAX_TOTAL_RESULTS or external_calls >= MAX_EXTERNAL_CALLS:
                break
            source = registry.get(source_name)
            if source is None:
                continue
            await _set_status(source_name, SourceStatus.SEARCHING.value)
            try:
                source_result = await source.search(query, profile)
                external_calls += 1
            except Exception as exc:
                logger.warning("Source %s failed on %r: %s", source_name, query, exc)
                await _set_status(source_name, SourceStatus.ERROR.value, error=str(exc)[:500])
                continue
            await _set_status(source_name, source_result.status.value, count=source_result.count, error=source_result.error)
            for job in source_result.jobs:
                if remote_filter == "remote" and job.remote_type != "remote":
                    continue
                if remote_filter == "hybrid" and job.remote_type == "onsite":
                    continue
                collected.append(job)

    canonical_groups = canonicalize_jobs(collected)
    logger.info(
        "session %d: %d raw results -> %d canonical jobs",
        session_id,
        len(collected),
        len(canonical_groups),
    )

    ranked: list[tuple[JobSearchResult, Job, list[str], Freshness, bool]] = []

    for group in canonical_groups:
        all_occurrences: list[NormalizedJob] = [group["job"]] + group["references"]
        best = _best_of(all_occurrences)
        fields = enrich(best.title, best.description, best.requirements, best.company, best.location)

        dedupe_key = fields["dedupe_key"] or f"{best.title.lower()}|{best.company.lower()}"

        job_row = (
            await db.execute(
                select(Job)
                .where(
                    (Job.dedupe_key == dedupe_key)
                    | (Job.canonical_url == best.canonical_url)
                    | (Job.source_url == best.source_url)
                )
                .order_by(Job.id.asc())
            )
        ).scalars().first()

        if job_row is None:
            company = await _get_or_create_company(db, best.company)
            job_row = Job(
                company_id=company.id,
                title=best.title[:255],
                description=best.description,
                requirements=best.requirements,
                location=best.location,
                country=best.country or fields["country"],
                job_type=_job_type_from_remote(best.remote_type),
                salary_min=best.salary_min,
                salary_max=best.salary_max,
                salary_currency=best.salary_currency or "USD",
                seniority=fields["seniority"],
                experience_min=fields["experience_min"],
                experience_max=fields["experience_max"],
                dedupe_key=dedupe_key,
                skills_required=fields["skills_required"],
                source=best.source,
                source_url=best.source_url,
                source_job_id=best.source_job_id,
                search_source=best.search_source,
                canonical_url=best.canonical_url,
                application_url=best.application_url or best.canonical_url,
                remote_type=best.remote_type,
                responsibilities=best.responsibilities,
                posted_at=best.posted_at,
                discovered_at=best.discovered_at or now,
                last_verified_at=now,
                is_active=True,
                posting_verified=best.posting_verified,
                embedding_id=None,
            )
            db.add(job_row)
            await db.flush()
        else:
            job_row.is_active = True
            job_row.last_verified_at = now
            if best.posted_at and not job_row.posted_at:
                job_row.posted_at = best.posted_at
            if best.remote_type:
                job_row.remote_type = best.remote_type
            if not job_row.canonical_url and best.canonical_url:
                job_row.canonical_url = best.canonical_url

        for occurrence in all_occurrences:
            exists = (
                await db.execute(
                    select(JobSourceReference).where(
                        JobSourceReference.job_id == job_row.id,
                        JobSourceReference.source == occurrence.source,
                        JobSourceReference.source_url == occurrence.source_url,
                    )
                )
            ).scalar_one_or_none()
            if not exists:
                db.add(
                    JobSourceReference(
                        job_id=job_row.id,
                        source=occurrence.source,
                        source_job_id=occurrence.source_job_id,
                        source_url=occurrence.source_url,
                        search_source=occurrence.search_source,
                        canonical_url=occurrence.canonical_url,
                        discovered_at=occurrence.discovered_at or now,
                        last_verified_at=now,
                        is_active=True,
                    )
                )

        freshness, posting_verified = classify_freshness(
            job_row.posted_at, job_row.updated_at, job_row.discovered_at, now=now
        )
        job_row.freshness = freshness.value
        job_row.posting_verified = posting_verified
        job_row.job_quality_score = job_quality_score(
            description=job_row.description,
            salary_min=job_row.salary_min,
            salary_max=job_row.salary_max,
            location=job_row.location,
            skills_required=job_row.skills_required,
            posting_verified=posting_verified,
            remote_type=job_row.remote_type,
        )

        match = match_job(
            profile=profile,
            title=job_row.title,
            description=job_row.description,
            requirements=job_row.requirements,
            skills=(job_row.skills_required.split(",") if job_row.skills_required else None),
            experience_min=job_row.experience_min,
            experience_max=job_row.experience_max,
            seniority=job_row.seniority,
            location=job_row.location,
            country=job_row.country,
            remote_type=job_row.remote_type,
            salary_min=job_row.salary_min,
            salary_max=job_row.salary_max,
            resume_text=resume_text,
        )
        score, explanation = rank_score(match, freshness, job_row.job_quality_score or 0)

        existing_result = (
            await db.execute(
                select(JobSearchResult).where(
                    JobSearchResult.session_id == session.id, JobSearchResult.job_id == job_row.id
                )
            )
        ).scalar_one_or_none()
        if existing_result:
            result = existing_result
        else:
            result = JobSearchResult(session_id=session.id, user_id=session.user_id, job_id=job_row.id)
            db.add(result)
        result.rank = 0
        result.overall_score = match.overall_score
        result.skill_score = match.skill_score
        result.experience_score = match.experience_score
        result.responsibility_score = match.responsibility_score
        result.seniority_score = match.seniority_score
        result.location_score = match.location_score
        result.salary_score = match.salary_score
        result.match_reason = _match_reason_text(match, score)
        result.matched_skills = json.dumps(match.matched_skills, ensure_ascii=False)
        result.missing_skills = json.dumps(match.missing_skills, ensure_ascii=False)
        result.related_skills = json.dumps(match.related_skills, ensure_ascii=False)
        result.recommendation = match.recommendation
        result.rank_explanation = explanation

        if career_facts:
            try:
                from app.services.advanced_match_service import compute_and_persist

                adv = await compute_and_persist(
                    db,
                    user_id=session.user_id,
                    job=job_row,
                    profile=profile,
                    facts=career_facts,
                    resume_text=resume_text,
                )
                result.match_confidence = adv.match_confidence
                counts = adv.requirement_counts()
                result.requirements_met = counts["met"]
                result.requirements_related = counts["related"]
                result.requirements_partial = counts["partial"]
                result.requirements_missing = counts["missing"]
                result.critical_missing = json.dumps(adv.critical_missing, ensure_ascii=False)
                result.advanced_json = json.dumps(adv.to_dict(), ensure_ascii=False)
            except Exception:
                logger.exception("advanced match failed for job %s", job_row.id)

        source_names = sorted({o.source for o in all_occurrences if o.source})
        ranked.append((result, job_row, source_names, freshness, posting_verified))

    ranked.sort(key=lambda item: item[0].overall_score, reverse=True)
    for idx, (result, _job, _sources, _freshness, _verified) in enumerate(ranked, start=1):
        result.rank = idx

    await db.flush()
    session.status = "COMPLETED"
    session.completed_at = datetime.utcnow()
    session.error = None
    await db.commit()
    logger.info("session %d completed with %d ranked results", session_id, len(ranked))


def _match_reason_text(match: Any, rank: int) -> str:
    parts = []
    if match.matched_skills:
        parts.append("Matched: " + ", ".join(match.matched_skills[:6]))
    if match.critical_missing:
        parts.append("Missing core: " + ", ".join(match.critical_missing[:4]))
    if not parts:
        parts.append(f"{match.overall_score}% overall match")
    return " | ".join(parts)


async def _get_or_create_company(db: AsyncSession, name: str | None) -> Company:
    normalized = (name or "Unknown").strip()[:255] or "Unknown"
    row = (await db.execute(select(Company).where(Company.name == normalized))).scalar_one_or_none()
    if row:
        return row
    company = Company(name=normalized)
    db.add(company)
    await db.flush()
    return company


async def get_session_with_status(db: AsyncSession, user_id: int, session_id: int) -> dict | None:
    session = (await db.execute(select(SearchSession).where(SearchSession.id == session_id))).scalar_one_or_none()
    if not session or session.user_id != user_id:
        return None
    statuses = (
        (await db.execute(select(SearchSourceStatus).where(SearchSourceStatus.session_id == session.id)))
        .scalars()
        .all()
    )
    queries = (await db.execute(select(SearchQuery).where(SearchQuery.session_id == session.id))).scalars().all()
    return {
        "search_id": session.id,
        "status": session.status,
        "time_range": session.time_range,
        "remote": session.remote_filter,
        "error": session.error,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "queries": [q.query for q in queries],
        "sources": [
            {
                "name": s.source,
                "portal": s.portal,
                "status": s.status,
                "count": s.count,
                "error": s.error,
            }
            for s in statuses
        ],
    }


async def get_search_results(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    *,
    time_range: str = "any",
    match_min: int = 0,
    source: str = "",
) -> list[dict]:
    session = (await db.execute(select(SearchSession).where(SearchSession.id == session_id))).scalar_one_or_none()
    if not session or session.user_id != user_id:
        return []
    rows = (
        await db.execute(
            select(JobSearchResult, Job, Company)
            .join(Job, JobSearchResult.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .where(JobSearchResult.session_id == session.id)
            .order_by(JobSearchResult.rank.asc())
        )
    ).all()

    out: list[dict] = []
    for result, job, company in rows:
        freshness, posting_verified = classify_freshness(
            job.posted_at, job.updated_at, job.discovered_at
        )
        if time_range and not within_time_range(time_range, freshness, posting_verified):
            continue
        if match_min and result.overall_score < match_min:
            continue

        refs = (
            (await db.execute(select(JobSourceReference).where(JobSourceReference.job_id == job.id)))
            .scalars()
            .all()
        )
        source_names = sorted({r.source for r in refs if r.source})
        primary_source = job.source or (source_names[0] if source_names else "Unknown")

        if source and source.casefold() not in {s.casefold() for s in source_names + [primary_source]}:
            continue

        out.append(
            _serialize_result(
                result=result,
                job=job,
                company=company,
                source_names=source_names,
                primary_source=primary_source,
                refs=[{"source": r.source, "source_url": r.source_url, "search_source": r.search_source} for r in refs],
                freshness=freshness,
            )
        )
    return out


def _serialize_result(
    *,
    result: JobSearchResult,
    job: Job,
    company: Company,
    source_names: list[str],
    primary_source: str,
    refs: list[dict],
    freshness: Freshness,
) -> dict:
    return {
        "id": job.id,
        "search_result_id": result.id,
        "rank": result.rank,
        "title": job.title,
        "company_name": company.name,
        "location": job.location,
        "country": job.country,
        "job_type": job.job_type.value if job.job_type else None,
        "remote_type": job.remote_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "description": job.description,
        "skills_required": job.skills_required,
        "seniority": job.seniority,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "posted_at": job.posted_at,
        "posting_verified": job.posting_verified,
        "discovered_at": job.discovered_at,
        "last_verified_at": job.last_verified_at,
        "freshness": freshness.value,
        "is_active": job.is_active,
        "source": primary_source,
        "search_source": job.search_source,
        "source_url": job.source_url,
        "canonical_url": job.canonical_url,
        "application_url": job.application_url,
        "sources": source_names,
        "source_references": refs,
        "match_score": result.overall_score,
        "skill_score": result.skill_score,
        "experience_score": result.experience_score,
        "responsibility_score": result.responsibility_score,
        "seniority_score": result.seniority_score,
        "location_score": result.location_score,
        "salary_score": result.salary_score,
        "matched_skills": _json_list(result.matched_skills),
        "missing_skills": _json_list(result.missing_skills),
        "related_skills": _json_list(result.related_skills),
        "recommendation": result.recommendation,
        "match_reason": result.match_reason,
        "job_quality_score": job.job_quality_score,
        "rank_explanation": result.rank_explanation,
        "match_confidence": result.match_confidence,
        "requirements": _advanced_counts(result),
        "evidence_count": _evidence_count(result),
    }


def _advanced_counts(result: JobSearchResult) -> dict | None:
    if result.advanced_json is None:
        return None
    try:
        json.loads(result.advanced_json)
    except (TypeError, ValueError):
        return None
    critical_missing: list[str] = []
    try:
        critical_missing = json.loads(result.critical_missing or "[]")
    except (TypeError, ValueError):
        critical_missing = []
    return {
        "met": result.requirements_met or 0,
        "related": result.requirements_related or 0,
        "partial": result.requirements_partial or 0,
        "missing": result.requirements_missing or 0,
        "critical_missing": critical_missing,
    }


def _evidence_count(result: JobSearchResult) -> int | None:
    if result.advanced_json is None:
        return None
    try:
        data = json.loads(result.advanced_json)
    except (TypeError, ValueError):
        return None
    return len(data.get("matched_facts", [])) if isinstance(data, dict) else None


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def user_search_history(db: AsyncSession, user_id: int, limit: int = 20) -> list[dict]:
    sessions = (
        (
            await db.execute(
                select(SearchSession)
                .where(SearchSession.user_id == user_id)
                .order_by(SearchSession.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for session in sessions:
        queries = (await db.execute(select(SearchQuery).where(SearchQuery.session_id == session.id))).scalars().all()
        result_count = (
            await db.execute(
                select(func.count(JobSearchResult.id)).where(JobSearchResult.session_id == session.id)
            )
        ).scalar_one()
        out.append(
            {
                "search_id": session.id,
                "status": session.status,
                "time_range": session.time_range,
                "remote": session.remote_filter,
                "queries": [q.query for q in queries],
                "result_count": result_count or 0,
                "created_at": session.created_at,
                "completed_at": session.completed_at,
            }
        )
    return out


async def delete_search_session(db: AsyncSession, user_id: int, session_id: int) -> bool:
    session = (await db.execute(select(SearchSession).where(SearchSession.id == session_id))).scalar_one_or_none()
    if not session or session.user_id != user_id:
        return False
    await db.delete(session)
    await db.commit()
    return True
