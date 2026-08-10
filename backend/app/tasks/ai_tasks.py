import asyncio
import logging

from celery import shared_task

from app.db.session import AsyncSessionLocal
from app.services.cover_letter_service import CoverLetterService
from app.services.interview_service import InterviewService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_cover_letter_task(self, user_id: int, job_id: int, resume_id: int | None = None):
    async def run():
        async with AsyncSessionLocal() as db:
            service = CoverLetterService(db)
            letter = await service.generate_cover_letter(user_id, job_id, resume_id)
            return letter.id

    letter_id = asyncio.run(run())
    return {"status": "generated", "letter_id": letter_id}


@shared_task(bind=True)
def generate_interview_questions_task(self, user_id: int, job_id: int, categories: list):
    async def run():
        async with AsyncSessionLocal() as db:
            service = InterviewService(db)
            questions = await service.generate_questions(user_id, job_id, list(categories))
            return len(questions)

    count = asyncio.run(run())
    return {"status": "generated", "question_count": count}
