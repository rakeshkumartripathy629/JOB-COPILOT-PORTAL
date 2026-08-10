from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationResponse

router = APIRouter()


@router.get("/", response_model=list[NotificationResponse])
async def list_notifications(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NotificationRepository(db)
    notifs = await repo.get_by_user(current_user.id)
    return [NotificationResponse.model_validate(n) for n in notifs]


@router.get("/unread-count")
async def unread_count(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NotificationRepository(db)
    count = await repo.count_unread(current_user.id)
    return {"unread": count}


@router.patch("/{notif_id}/read")
async def mark_read(
    notif_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NotificationRepository(db)
    notif = await repo.get(notif_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    await repo.update(notif_id, {"is_read": 1})
    return {"detail": "Marked as read"}


@router.post("/read-all")
async def mark_all_read(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NotificationRepository(db)
    updated = await repo.mark_all_read(current_user.id)
    return {"detail": f"Marked {updated} notifications as read"}


@router.delete("/{notif_id}", status_code=204)
async def delete_notification(
    notif_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NotificationRepository(db)
    notif = await repo.get(notif_id)
    if not notif or notif.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    await repo.delete(notif_id)
    return None
