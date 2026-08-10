from datetime import datetime

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    job_id: int
    application_source: str | None = Field(None, pattern="^(JOB_SEARCH|SAVED_JOB|RECOMMENDATION|MANUAL|EXTENSION|AUTO_APPLY)$")
    priority: str | None = Field(None, pattern="^(HIGH|MEDIUM|LOW)$")
    resume_id: int | None = None
    resume_version_id: int | None = None
    tailored_resume_id: int | None = None
    cover_letter_id: int | None = None
    application_answer_version_id: int | None = None
    application_packet_id: int | None = None
    tags: list[str] | None = None


class ApplicationUpdate(BaseModel):
    notes: str | None = None
    priority: str | None = Field(None, pattern="^(HIGH|MEDIUM|LOW)$")


class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(DRAFT|READY|APPLIED|VIEWED|RECRUITER_CONTACT|ASSESSMENT|INTERVIEW|TECHNICAL_ROUND|FINAL_ROUND|OFFER|REJECTED|WITHDRAWN|EXPIRED|FAILED|UNKNOWN)$")
    reason: str | None = None


class NoteCreate(BaseModel):
    note: str = Field(..., min_length=1)


class TagCreate(BaseModel):
    tag: str = Field(..., min_length=1, max_length=100)


class ReminderCreate(BaseModel):
    reminder_type: str = Field(..., pattern="^(FOLLOW_UP|INTERVIEW|ASSESSMENT_DEADLINE|RECRUITER_RESPONSE)$")
    due_at: datetime


class FollowUpRequest(BaseModel):
    mode: str = Field("professional", pattern="^(professional|short|friendly)$")


class ApplicationSnapshotOut(BaseModel):
    job_title: str
    company_name: str | None = None
    location: str | None = None
    country: str | None = None
    remote_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    source: str | None = None
    source_url: str | None = None
    application_url: str | None = None
    canonical_url: str | None = None
    posted_at: datetime | None = None
    match_score: int | None = None
    match_confidence: int | None = None
    job_quality_score: int | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    status: str
    applied_at: datetime | None = None
    responded_at: datetime | None = None
    application_source: str
    priority: str
    ai_priority: str | None = None
    resume_id: int | None = None
    resume_version_id: int | None = None
    tailored_resume_id: int | None = None
    cover_letter_id: int | None = None
    cover_letter_version_id: int | None = None
    application_answer_version_id: int | None = None
    application_packet_id: int | None = None
    notes: str | None = None
    follow_up_recommended_at: datetime | None = None
    follow_up_reason: str | None = None
    follow_up_status: str | None = None
    job_title: str | None = None
    company_name: str | None = None
    match_score: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ApplicationDetailResponse(ApplicationResponse):
    snapshot: ApplicationSnapshotOut | None = None
    tags: list[str] = []
    documents: list[dict] = []
    timeline: list[dict] = []
