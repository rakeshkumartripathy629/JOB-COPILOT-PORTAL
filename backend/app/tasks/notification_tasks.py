import logging
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import select

from app.db.models.application import Application, ApplicationStatus
from app.db.models.notification import Notification, NotificationType
from app.db.session import AsyncSessionLocal
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def send_interview_reminder(self, user_id: int, job_id: int):
    async def run():
        async with AsyncSessionLocal() as db:
            service = NotificationService(db)
            await service.create_notification(
                user_id, NotificationType.INTERVIEW_REMINDER, "Upcoming Interview", f"Reminder for job {job_id}"
            )

    asyncio_run(run())
    return {"status": "sent"}


@shared_task(bind=True)
def scan_due_reminders(self):
    """Create follow-up reminders for applications that have not been responded to within 7 days."""

    async def run():
        async with AsyncSessionLocal() as db:
            cutoff = datetime.utcnow() - timedelta(days=7)
            result = await db.execute(
                select(Application).where(
                    Application.status == ApplicationStatus.PENDING,
                    Application.applied_at.isnot(None),
                    Application.applied_at < cutoff,
                )
            )
            due = result.scalars().all()
            created = 0
            for app in due:
                already = await db.execute(
                    select(Notification).where(
                        Notification.user_id == app.user_id,
                        Notification.type == NotificationType.FOLLOW_UP,
                        Notification.created_at > cutoff,
                    )
                )
                if already.scalar_one_or_none():
                    continue
                service = NotificationService(db)
                await service.create_notification(
                    app.user_id,
                    NotificationType.FOLLOW_UP,
                    "Follow up reminder",
                    f"It has been over a week since you applied to job #{app.job_id}. Consider a follow-up.",
                )
                created += 1
            await db.commit()
            logger.info("scan_due_reminders completed, %d follow-ups created", created)

    asyncio_run(run())
    return {"status": "scanned"}


def asyncio_run(coro):
    import asyncio

    asyncio.run(coro)
