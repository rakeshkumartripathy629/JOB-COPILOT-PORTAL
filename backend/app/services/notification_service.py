from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification, NotificationType
from app.repositories.notification_repo import NotificationRepository


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.notif_repo = NotificationRepository(db)

    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str | None = None,
    ) -> Notification:
        return await self.notif_repo.create(
            {
                "user_id": user_id,
                "type": notification_type,
                "title": title,
                "message": message,
            }
        )

    async def notify(self, user_id: int, notification_type: NotificationType, title: str, message: str) -> None:
        try:
            await self.create_notification(user_id, notification_type, title, message)
            await self.notif_repo.db.commit()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Failed to create notification")
