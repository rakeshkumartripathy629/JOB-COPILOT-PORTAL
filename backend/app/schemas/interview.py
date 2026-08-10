from datetime import datetime

from pydantic import BaseModel, Field


class InterviewQuestionCreate(BaseModel):
    job_id: int
    categories: list[str] = Field(default_factory=list)


class InterviewQuestionResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    category: str
    question: str
    suggested_answer: str | None = None
    explanation: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=5, max_length=4000)


class InterviewEvaluationResponse(BaseModel):
    question_id: int
    score: int
    strengths: str
    improvements: str
    model_answer: str
