from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.user import ProfileUpdate, UserWithProfile
from app.services.user_service import UserService

router = APIRouter()


@router.get("/me", response_model=UserWithProfile)
async def get_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.get_user(current_user.id)
    return UserWithProfile.model_validate(user)


@router.patch("/me", response_model=UserWithProfile)
async def update_me(
    data: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    await service.update_profile(current_user.id, data)
    user = await service.get_user(current_user.id)
    return UserWithProfile.model_validate(user)
