from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewEvaluationResponse,
    InterviewQuestionCreate,
    InterviewQuestionResponse,
)
from app.services.interview_service import InterviewService

router = APIRouter()


@router.post("/questions", response_model=list[InterviewQuestionResponse], status_code=201)
async def generate_questions(
    data: InterviewQuestionCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewService(db)
    questions = await service.generate_questions(current_user.id, data.job_id, data.categories)
    return [InterviewQuestionResponse.model_validate(q) for q in questions]


@router.get("/questions", response_model=list[InterviewQuestionResponse])
async def list_questions(
    job_id: int | None = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.interview_repo import InterviewRepository

    repo = InterviewRepository(db)
    if job_id:
        questions = await repo.get_by_user_and_job(current_user.id, job_id)
    else:
        questions = await repo.get_by_user(current_user.id)
    return [InterviewQuestionResponse.model_validate(q) for q in questions]


@router.post("/questions/{question_id}/evaluate", response_model=InterviewEvaluationResponse)
async def evaluate_answer(
    question_id: int,
    data: InterviewAnswerRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewService(db)
    return await service.evaluate_answer(current_user.id, question_id, data.answer)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.interview_repo import InterviewRepository

    repo = InterviewRepository(db)
    question = await repo.get(question_id)
    if not question or question.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Question not found")
    await repo.delete(question_id)
    return None
