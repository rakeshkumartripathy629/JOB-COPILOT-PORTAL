from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: AsyncSession):
        super().__init__(Notification, db)

    async def get_by_user(self, user_id: int) -> list[Notification]:
        result = await self.db.execute(select(Notification).where(Notification.user_id == user_id))
        return list(result.scalars().all())

    async def get_unread_by_user(self, user_id: int) -> list[Notification]:
        result = await self.db.execute(
            select(Notification).where(Notification.user_id == user_id, Notification.is_read == 0)
        )
        return list(result.scalars().all())

    async def count_unread(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read == 0)
        )
        return result.scalar_one() or 0

    async def mark_all_read(self, user_id: int) -> int:
        result = await self.db.execute(
            update(Notification).where(Notification.user_id == user_id, Notification.is_read == 0).values(is_read=1)
        )
        await self.db.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]
