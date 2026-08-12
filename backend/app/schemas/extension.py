"""Chrome Extension API schemas.

All inputs are validated; all values returned are scoped to the authenticated user.
Sensitive field values are never persisted or logged server-side.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtensionSessionCreate(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    page_url: str | None = Field(default=None, max_length=2000)
    job_title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    ats: str | None = Field(default=None, max_length=100)
    job_id: int | None = None
    status: str = Field(default="DETECTED", max_length=30)


class ExtensionSessionOut(BaseModel):
    session_id: str
    user_id: int
    status: str
    page_url: str | None = None
    job_title: str | None = None
    company: str | None = None
    ats: str | None = None
    job_id: int | None = None
    application_id: int | None = None
    applied_before: bool = False
    applied_at: str | None = None
    application_status: str | None = None


class DetectJobRequest(BaseModel):
    page_url: str | None = Field(default=None, max_length=2000)
    job_title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    canonical_url: str | None = Field(default=None, max_length=2000)
    source_job_id: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=20000)


class DetectedJobOut(BaseModel):
    matched: bool
    job_id: int | None = None
    title: str | None = None
    company: str | None = None
    match_confidence: float = 0.0
    location: str | None = None
    canonical_url: str | None = None
    applied_before: bool = False
    applied_at: str | None = None
    application_status: str | None = None


class DetectAtsRequest(BaseModel):
    detected: str | None = Field(default=None, max_length=100)
    url: str | None = Field(default=None, max_length=2000)
    signals: list[str] = Field(default_factory=list, max_length=20)


class DetectAtsOut(BaseModel):
    ats: str
    confidence: float
    signals: list[str]


class FieldDetected(BaseModel):
    field_type: str = Field(..., max_length=50)
    label: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    element_id: str | None = Field(default=None, max_length=255)
    placeholder: str | None = Field(default=None, max_length=255)
    autocomplete: str | None = Field(default=None, max_length=50)
    detection_method: str = Field(default="dom", max_length=50)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    max_length: int | None = Field(default=None, ge=1, le=100000)
    sensitive: bool = False
    required: bool = False


class AnalyzeFieldsRequest(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    fields: list[FieldDetected] = Field(default_factory=list, max_length=200)
    job: DetectJobRequest | None = None


class FieldValueOut(BaseModel):
    field_type: str
    value: str | None = None
    confidence: float = 0.0
    value_source: str = "UNKNOWN"
    needs_review: bool = False
    reason: str | None = None


class AnalyzeFieldsOut(BaseModel):
    session_id: str
    fields: list[FieldValueOut]


class PacketResumeOut(BaseModel):
    id: int
    title: str
    file_type: str | None = None
    ats_score: int | None = None
    version_label: str | None = None


class PacketCoverLetterOut(BaseModel):
    id: int
    content: str
    created_at: str | None = None


class ApplicationPacketOut(BaseModel):
    job_id: int
    title: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    match_score: int | None = None
    resumes: list[PacketResumeOut] = Field(default_factory=list)
    cover_letters: list[PacketCoverLetterOut] = Field(default_factory=list)
    recommended_resume_id: int | None = None
    recommended_resume_label: str | None = None
    recommendation_reason: str | None = None


class GenerateAnswerRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    job_id: int | None = None
    job: DetectJobRequest | None = None
    max_length: int | None = Field(default=None, ge=1, le=10000)


class AnswerOut(BaseModel):
    answer: str | None = None
    confidence: float = 0.0
    needs_review: bool = True
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None


class ValidateAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=10000)
    question: str | None = Field(default=None, max_length=2000)


class ValidateAnswerOut(BaseModel):
    valid: bool
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)


class FillLogCreate(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    fields_detected: int = Field(default=0, ge=0)
    fields_filled: int = Field(default=0, ge=0)
    fields_skipped: int = Field(default=0, ge=0)
    fields_reviewed: int = Field(default=0, ge=0)
    fields_failed: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=20)


class FillLogOut(BaseModel):
    logged: bool
    fill_log_id: int | None = None


class ExtensionLogCreate(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    level: str = Field(default="info", max_length=10)
    event: str = Field(..., min_length=1, max_length=100)
    message: str | None = Field(default=None, max_length=500)


class ExtensionLogOut(BaseModel):
    logged: bool


class AnswerAndValidation(BaseModel):
    answer: str | None = None
    confidence: float = 0.0
    needs_review: bool = True
    evidence: list[str] = Field(default_factory=list)
    validation: ValidateAnswerOut | None = None
    reason: str | None = None
