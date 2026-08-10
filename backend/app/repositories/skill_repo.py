from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.skill import Skill
from app.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    def __init__(self, db: AsyncSession):
        super().__init__(Skill, db)

    async def get_by_name(self, name: str) -> Skill | None:
        result = await self.db.execute(select(Skill).where(Skill.name == name))
        return result.scalar_one_or_none()

    async def bulk_create(self, skills: list[str]):
        existing = await self.db.execute(select(Skill.name))
        known = {row[0] for row in existing.all()}
        missing = [{"name": s} for s in skills if s not in known]
        if missing:
            await self.db.execute(insert(Skill).values(missing))
            await self.db.commit()
