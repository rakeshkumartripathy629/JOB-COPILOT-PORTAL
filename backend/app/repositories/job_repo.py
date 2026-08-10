from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    def __init__(self, db: AsyncSession):
        super().__init__(Job, db)

    async def search(
        self,
        query: str = "",
        location: str = "",
        country: str = "",
        remote_only: bool = False,
        salary_min: int = 0,
        experience_level: str = "",
        skills: list | None = None,
        page: int = 1,
        limit: int = 20,
    ):
        stmt = select(Job, Company).join(Company)

        if query:
            stmt = stmt.where(Job.title.ilike(f"%{query}%"))
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if country:
            stmt = stmt.where(Job.country.ilike(f"%{country}%"))
        if remote_only:
            stmt = stmt.where(Job.job_type == JobType.REMOTE)
        if salary_min:
            stmt = stmt.where(Job.salary_min >= salary_min)
        if experience_level:
            stmt = stmt.where(Job.experience_level == experience_level)

        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        return result.all()

    async def get_by_id(self, job_id: int):
        result = await self.db.execute(select(Job, Company).join(Company).where(Job.id == job_id))
        return result.first()

    async def get_by_source_url(self, source: str, source_url: str):
        stmt = select(Job).where(Job.source == source, Job.source_url == source_url)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_dedupe_key(self, dedupe_key: str):
        stmt = select(Job).where(Job.dedupe_key == dedupe_key).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
