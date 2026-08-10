from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resume import Resume
from app.db.models.resume_version import ResumeVersion
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    def __init__(self, db: AsyncSession):
        super().__init__(Resume, db)

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100):
        result = await self.db.execute(select(Resume).where(Resume.user_id == user_id).offset(skip).limit(limit))
        return result.scalars().all()

    async def create_version(self, version_in: dict) -> ResumeVersion:
        version = ResumeVersion(**version_in)
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version


class ResumeVersionRepository(BaseRepository[ResumeVersion]):
    def __init__(self, db: AsyncSession):
        super().__init__(ResumeVersion, db)
