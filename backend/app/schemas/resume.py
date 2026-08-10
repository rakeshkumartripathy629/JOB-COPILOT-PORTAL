from datetime import datetime

from pydantic import BaseModel, Field


class ResumeUpload(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    title: str
    file_path: str
    file_type: str
    parsed_data: str | None = None
    ats_score: int | None = None
    missing_keywords: str | None = None
    improvement_suggestions: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeDetail(ResumeResponse):
    pass


class ResumeVersionCreate(BaseModel):
    version_label: str | None = Field(None, max_length=255)
    content: str


class ResumeVersionResponse(BaseModel):
    id: int
    resume_id: int
    user_id: int
    content: str
    version_label: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
