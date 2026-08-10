import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from app.agents.resume_agent import resume_agent
from app.config import settings
from app.db.models.resume import Resume
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def parse_resume_task(self, resume_id: int):
    async def run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Resume).where(Resume.id == resume_id))
            resume = result.scalar_one_or_none()
            if not resume:
                return {"resume_id": resume_id, "status": "not_found"}
            await resume_agent.ainvoke(
                {
                    "db": db,
                    "resume_id": resume_id,
                    "file_path": resume.file_path,
                    "raw_text": "",
                    "parsed_data": "",
                    "ats_score": 0,
                    "missing_keywords": "",
                    "suggestions": "",
                    "error": None,
                }
            )
            if settings.ENABLE_RESUME_JOB_FETCH:
                from app.services.resume_job_service import auto_fetch_matches_for_resume

                await auto_fetch_matches_for_resume(resume_id)
            return {"resume_id": resume_id, "status": "parsed"}

    asyncio.run(run())
    return {"resume_id": resume_id, "status": "parsed"}
