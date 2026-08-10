from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profile_repo import ProfileRepository
from app.repositories.user_repo import UserRepository
from app.schemas.user import ProfileUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)
        self.profile_repo = ProfileRepository(db)

    async def get_user(self, user_id: int):
        return await self.user_repo.get_with_profile(user_id)

    async def update_profile(self, user_id: int, data: ProfileUpdate):
        profile = await self.profile_repo.get_by_user(user_id)
        if not profile:
            profile = await self.profile_repo.create({"user_id": user_id})
        return await self.profile_repo.update(profile.id, data.model_dump())
