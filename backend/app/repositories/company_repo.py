from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    def __init__(self, db: AsyncSession):
        super().__init__(Company, db)

    async def get_by_name(self, name: str):
        result = await self.db.execute(select(Company).where(Company.name == name))
        return result.scalar_one_or_none()
