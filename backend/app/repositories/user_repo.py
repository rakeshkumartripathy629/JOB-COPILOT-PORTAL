from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.user import User, user_skills
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_with_profile(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).options(selectinload(User.profile)).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_skills(self, user_id: int):
        result = await self.db.execute(select(user_skills).where(user_skills.c.user_id == user_id))
        return result.all()
