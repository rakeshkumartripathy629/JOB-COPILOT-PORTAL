from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cover_letter_agent import cover_letter_agent
from app.db.models.cover_letter import CoverLetter
from app.repositories.cover_letter_repo import CoverLetterRepository
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.services.llm_service import LLMError


class CoverLetterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cover_repo = CoverLetterRepository(db)
        self.job_repo = JobRepository(db)
        self.resume_repo = ResumeRepository(db)

    async def generate_cover_letter(self, user_id: int, job_id: int, resume_id: int | None = None) -> CoverLetter:
        result = await self.job_repo.get_by_id(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        resume = await self.resume_repo.get(resume_id) if resume_id else None
        if resume_id and not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        if resume and resume.user_id != user_id:
            raise HTTPException(status_code=403, detail="Resume does not belong to you")

        try:
            agent_result: dict[str, Any] = await cover_letter_agent.ainvoke(
                {
                    "db": self.db,
                    "user_id": user_id,
                    "job_id": job_id,
                    "resume_id": resume_id,
                    "context": {},
                    "draft": "",
                    "final": "",
                }
            )
        except LLMError:
            raise HTTPException(status_code=502, detail="AI service unavailable. Please try again later.") from None

        content = agent_result.get("final") or agent_result.get("draft")
        if not content:
            raise HTTPException(
                status_code=502, detail="AI service returned an empty response. Please try again later."
            )

        letter = await self.cover_repo.create(
            {
                "user_id": user_id,
                "job_id": job_id,
                "resume_id": resume_id,
                "content": content,
            }
        )
        from app.db.models.notification import NotificationType
        from app.services.notification_service import NotificationService

        job, _ = result
        await NotificationService(self.db).notify(
            user_id,
            NotificationType.SYSTEM,
            "Cover letter generated",
            f"Your cover letter for {job.title} is ready to review.",
        )
        return letter
