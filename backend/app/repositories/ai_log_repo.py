from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_log import AiLog
from app.repositories.base import BaseRepository


class AiLogRepository(BaseRepository[AiLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AiLog, db)

    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100):
        result = await self.db.execute(select(AiLog).where(AiLog.user_id == user_id).offset(skip).limit(limit))
        return result.scalars().all()
