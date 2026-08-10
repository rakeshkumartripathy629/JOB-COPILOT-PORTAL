"""Fetch real jobs matching a resume's designation + skills and upsert them into the DB."""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.resume import Resume
from app.db.session import AsyncSessionLocal
from app.services.job_search_service import JobSearchService

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = ["software engineer", "backend developer", "data scientist"]
MAX_QUERIES = 3
MAX_SKILLS = 3


def parse_parsed_data(resume: Resume) -> dict[str, Any]:
    """Best-effort JSON parse of resume.parsed_data."""
    if not resume or not resume.parsed_data:
        return {}
    try:
        data = json.loads(resume.parsed_data)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def build_queries(parsed: dict[str, Any], limit: int = MAX_QUERIES) -> list[str]:
    """Build job search queries from a resume's designation and top skills."""
    designation = str(parsed.get("designation") or "").strip()
    skills = [str(s).strip() for s in (parsed.get("skills") or []) if str(s).strip()]
    queries: list[str] = []
    if designation:
        queries.append(designation)
    for skill in skills[:MAX_SKILLS]:
        if designation and len(queries) < limit:
            queries.append(f"{designation} {skill}")
    if not queries:
        queries = list(DEFAULT_QUERIES)
    return queries[:limit]


async def fetch_jobs_for_resume(db: AsyncSession, resume: Resume) -> dict:
    """Fetch India jobs for the resume's designation and skills. Skips when disabled."""
    if not settings.ENABLE_RESUME_JOB_FETCH:
        logger.info("resume job auto-fetch disabled")
        return {"added": 0, "per_source": {}}
    parsed = parse_parsed_data(resume)
    queries = build_queries(parsed)
    service = JobSearchService(db)
    result = await service.fetch_india(queries)
    logger.info(
        "resume auto-fetch: resume_id=%s designation=%r added=%d queries=%r",
        resume.id,
        parsed.get("designation"),
        result["added"],
        queries,
    )
    return result


async def fetch_jobs_for_latest_resume(db: AsyncSession, user_id: int) -> dict:
    """Fetch India jobs for a user's most recent resume, or default queries if none exists."""
    from sqlalchemy import select

    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume:
        return await fetch_jobs_for_resume(db, resume)
    if not settings.ENABLE_RESUME_JOB_FETCH:
        return {"added": 0, "per_source": {}}
    service = JobSearchService(db)
    return await service.fetch_india(list(DEFAULT_QUERIES))


async def auto_fetch_matches_for_resume(resume_id: int) -> dict:
    """Background-task wrapper that opens its own DB session and fetches matching India jobs."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if not resume:
            return {"added": 0, "per_source": {}}
        return await fetch_jobs_for_resume(db, resume)
