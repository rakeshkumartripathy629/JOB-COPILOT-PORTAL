import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.skill_repo import SkillRepository
from app.services.llm_service import LLMError, LLMService

logger = logging.getLogger(__name__)


def _score(value: Any, default: int = 0) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


class MatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.job_repo = JobRepository(db)
        self.resume_repo = ResumeRepository(db)
        self.skill_repo = SkillRepository(db)
        self.llm = LLMService()

    async def match_job_for_resume(self, resume_id: int, job_id: int) -> dict:
        resume = await self.resume_repo.get(resume_id)
        if not resume:
            raise ValueError("Resume not found")
        result = await self.job_repo.get_by_id(job_id)
        if not result:
            raise ValueError("Job not found")
        job, _ = result

        prompt = (
            "Compare this resume with the job description and return a JSON object with keys:\n"
            "- skill_match_percentage (0-100)\n"
            "- experience_match_percentage (0-100)\n"
            "- education_match_percentage (0-100)\n"
            "- overall_score (0-100)\n"
            "- missing_skills (list of strings)\n"
            "- suggestions (list of strings)\n\n"
            f"Resume data: {resume.parsed_data}\n"
            f"Job title: {job.title}\n"
            f"Job description: {job.description}\n"
            f"Job requirements: {job.requirements}\n"
        )
        try:
            raw = await self.llm.generate_json(prompt)
        except LLMError as e:
            logger.error("Match analysis failed: %s", e)
            raw = {}

        return {
            "skill_match_percentage": _score(raw.get("skill_match_percentage")),
            "experience_match_percentage": _score(raw.get("experience_match_percentage")),
            "education_match_percentage": _score(raw.get("education_match_percentage")),
            "overall_score": _score(raw.get("overall_score")),
            "missing_skills": raw.get("missing_skills", []),
            "suggestions": raw.get("suggestions", []),
        }
