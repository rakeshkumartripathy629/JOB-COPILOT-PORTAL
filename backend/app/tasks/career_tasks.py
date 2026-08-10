"""Celery tasks for the career evidence system (idempotent)."""

import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from app.db.models.job import Job
from app.db.session import AsyncSessionLocal
from app.services.advanced_match_service import compute_and_persist
from app.services.career_evidence_service import ensure_career_vault, get_resume_facts, rebuild_career_vault
from app.services.search_profile_service import build_search_profile

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def index_career_vault_task(self, user_id: int):
    async def run() -> dict:
        async with AsyncSessionLocal() as db:
            return await rebuild_career_vault(db, user_id)

    try:
        return asyncio.run(run())
    except Exception as exc:
        logger.exception("career vault index failed for user %s", user_id)
        return {"user_id": user_id, "error": str(exc)}


@shared_task(bind=True)
def compute_job_match_task(self, user_id: int, job_id: int):
    async def run() -> dict:
        async with AsyncSessionLocal() as db:
            from app.db.models.user import User

            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
            if user is None or job is None:
                return {"user_id": user_id, "job_id": job_id, "status": "not_found"}
            profile = await build_search_profile(db, user)
            if profile is None:
                return {"user_id": user_id, "job_id": job_id, "status": "no_resume"}
            await ensure_career_vault(db, user_id)
            facts = await get_resume_facts(db, user_id)
            match = await compute_and_persist(db, user_id=user_id, job=job, profile=profile, facts=facts)
            await db.commit()
            return {
                "user_id": user_id,
                "job_id": job_id,
                "status": "computed",
                "overall_score": match.overall_score,
                "match_confidence": match.match_confidence,
            }

    return asyncio.run(run())
