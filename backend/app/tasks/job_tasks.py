import asyncio
import logging
from datetime import datetime

from celery import shared_task
from sqlalchemy import func, select

from app.db.models.job import Job
from app.db.session import AsyncSessionLocal
from app.services.job_search_service import JobSearchService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def fetch_and_ingest_jobs(self, provider: str, query: str):
    async def run():
        async with AsyncSessionLocal() as db:
            service = JobSearchService(db)
            if provider == "adzuna":
                await service.fetch_from_adzuna(query)
            elif provider == "jsearch":
                await service.fetch_from_jsearch(query)

    asyncio.run(run())
    return {"provider": provider, "query": query, "status": "ingested"}


@shared_task(bind=True)
def refresh_expired_jobs(self):
    async def run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count(Job.id)).where(Job.expires_at.isnot(None), Job.expires_at < datetime.utcnow())
            )
            expired = result.scalar_one() or 0
            logger.info("refresh_expired_jobs: %d expired jobs", expired)
            return expired

    expired = asyncio.run(run())
    return {"status": "ok", "expired_jobs": expired}
