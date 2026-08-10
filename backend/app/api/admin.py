from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.repositories.ai_log_repo import AiLogRepository
from app.repositories.user_repo import UserRepository

router = APIRouter()


@router.get("/users")
async def list_users(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.is_superuser:
        from app.middleware.error_handler import AppException

        raise AppException(403, "Forbidden")
    repo = UserRepository(db)
    users = await repo.get_all()
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active} for u in users]


@router.get("/ai-logs")
async def list_ai_logs(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.is_superuser:
        from app.middleware.error_handler import AppException

        raise AppException(403, "Forbidden")
    repo = AiLogRepository(db)
    logs = await repo.get_all()
    return [
        {
            "id": entry.id,
            "user_id": entry.user_id,
            "agent_type": entry.agent_type,
            "status": entry.status,
            "created_at": entry.created_at,
        }
        for entry in logs
    ]


@router.get("/activity-logs")
async def list_activity_logs(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.is_superuser:
        from app.middleware.error_handler import AppException

        raise AppException(403, "Forbidden")
    from app.repositories.activity_log_repo import ActivityLogRepository

    repo = ActivityLogRepository(db)
    logs = await repo.get_all()
    return [
        {"id": entry.id, "action": entry.action, "entity_type": entry.entity_type, "created_at": entry.created_at}
        for entry in logs
    ]
