from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cover_letter import CoverLetter
from app.repositories.base import BaseRepository


class CoverLetterRepository(BaseRepository[CoverLetter]):
    def __init__(self, db: AsyncSession):
        super().__init__(CoverLetter, db)

    async def get_by_user(self, user_id: int) -> list[CoverLetter]:
        result = await self.db.execute(select(CoverLetter).where(CoverLetter.user_id == user_id))
        return list(result.scalars().all())

    async def get_by_user_and_job(self, user_id: int, job_id: int) -> CoverLetter | None:
        result = await self.db.execute(
            select(CoverLetter).where(CoverLetter.user_id == user_id, CoverLetter.job_id == job_id)
        )
        return result.scalar_one_or_none()
