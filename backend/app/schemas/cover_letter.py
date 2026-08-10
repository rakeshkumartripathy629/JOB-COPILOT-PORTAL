from datetime import datetime

from pydantic import BaseModel, Field


class CoverLetterCreate(BaseModel):
    job_id: int
    resume_id: int | None = None


class CoverLetterUpdate(BaseModel):
    content: str | None = Field(None, min_length=1)
    status: str | None = None


class CoverLetterResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    resume_id: int | None = None
    content: str
    status: str
    job_title: str | None = None
    company_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
