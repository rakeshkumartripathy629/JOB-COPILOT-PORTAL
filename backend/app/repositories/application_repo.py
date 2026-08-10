from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.application import Application, ApplicationStatus
from app.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):
    def __init__(self, db: AsyncSession):
        super().__init__(Application, db)

    async def get_by_user(self, user_id: int, status: ApplicationStatus | None = None):
        stmt = select(Application).where(Application.user_id == user_id)
        if status:
            stmt = stmt.where(Application.status == status)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_user_and_job(self, user_id: int, job_id: int):
        result = await self.db.execute(
            select(Application).where(Application.user_id == user_id, Application.job_id == job_id)
        )
        return result.scalar_one_or_none()
