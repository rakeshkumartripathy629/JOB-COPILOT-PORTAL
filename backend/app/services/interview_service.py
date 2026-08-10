from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.interview_agent import interview_agent
from app.db.models.interview_question import InterviewQuestion, QuestionCategory
from app.repositories.interview_repo import InterviewRepository
from app.repositories.job_repo import JobRepository
from app.services.llm_service import LLMError, LLMService

VALID_CATEGORIES = {category.value for category in QuestionCategory}


class InterviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.interview_repo = InterviewRepository(db)
        self.job_repo = JobRepository(db)

    async def generate_questions(self, user_id: int, job_id: int, categories: list[str]) -> list[InterviewQuestion]:
        result = await self.job_repo.get_by_id(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")

        unknown = [c for c in categories if c not in VALID_CATEGORIES]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unsupported category: {', '.join(unknown)}")
        if not categories:
            categories = ["technical", "behavioral"]

        try:
            agent_result = await interview_agent.ainvoke(
                {
                    "db": self.db,
                    "user_id": user_id,
                    "job_id": job_id,
                    "categories": categories,
                    "questions": [],
                }
            )
        except LLMError:
            raise HTTPException(status_code=502, detail="AI service unavailable. Please try again later.") from None

        items = agent_result.get("questions") or []
        created: list[InterviewQuestion] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("question"):
                continue
            created.append(
                await self.interview_repo.create(
                    {
                        "user_id": user_id,
                        "job_id": job_id,
                        "category": item.get("category") or categories[0],
                        "question": item["question"],
                        "suggested_answer": item.get("suggested_answer"),
                        "explanation": item.get("explanation"),
                    }
                )
            )
        if created:
            from app.db.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            job, _ = result
            await NotificationService(self.db).notify(
                user_id,
                NotificationType.INTERVIEW_REMINDER,
                "Interview questions ready",
                f"Generated {len(created)} practice questions for {job.title}.",
            )
        return created

    async def evaluate_answer(self, user_id: int, question_id: int, answer: str) -> dict[str, object]:
        question = await self.interview_repo.get(question_id)
        if not question or question.user_id != user_id:
            raise HTTPException(status_code=404, detail="Question not found")

        prompt = (
            f"Question ({question.category}): {question.question}\n\n"
            f"Suggested answer: {question.suggested_answer or 'Not provided'}\n\n"
            f"Candidate's answer:\n{answer}\n\n"
            "Act as a strict but fair interviewer. Score the answer 0-100 and return ONLY JSON: "
            '{"score": <0-100 int>, "strengths": "<1-2 sentences>", '
            '"improvements": "<1-2 sentences on what to improve>", "model_answer": "<a strong model answer>"}.'
        )
        try:
            payload = await LLMService().generate_json(prompt)
        except LLMError:
            raise HTTPException(status_code=502, detail="AI service unavailable. Please try again later.") from None

        score = payload.get("score")
        if not isinstance(score, int | float):
            score = 0
        return {
            "question_id": question.id,
            "score": max(0, min(100, round(score))),
            "strengths": str(payload.get("strengths") or "").strip(),
            "improvements": str(payload.get("improvements") or "").strip(),
            "model_answer": str(payload.get("model_answer") or "").strip(),
        }
