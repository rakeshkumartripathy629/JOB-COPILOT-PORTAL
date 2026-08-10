from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.interview_question import InterviewQuestion
from app.repositories.base import BaseRepository


class InterviewRepository(BaseRepository[InterviewQuestion]):
    def __init__(self, db: AsyncSession):
        super().__init__(InterviewQuestion, db)

    async def get_by_user(self, user_id: int) -> list[InterviewQuestion]:
        result = await self.db.execute(select(InterviewQuestion).where(InterviewQuestion.user_id == user_id))
        return list(result.scalars().all())

    async def get_by_user_and_job(self, user_id: int, job_id: int):
        result = await self.db.execute(
            select(InterviewQuestion).where(InterviewQuestion.user_id == user_id, InterviewQuestion.job_id == job_id)
        )
        return result.scalars().all()
