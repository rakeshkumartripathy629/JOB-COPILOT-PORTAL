from datetime import datetime

from pydantic import BaseModel, Field


class JobSearch(BaseModel):
    query: str = Field(default="", max_length=255)
    location: str | None = Field(None, max_length=255)
    country: str | None = Field(None, max_length=100)
    remote_only: bool | None = False
    salary_min: int | None = None
    experience_level: str | None = Field(None, max_length=100)
    skills: list[str] | None = None
    page: int = 1
    limit: int = Field(default=20, le=50)


class JobResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    location: str | None = None
    country: str | None = None
    job_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    experience_level: str | None = None
    seniority: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    skills_required: str | None = None
    source: str | None = None
    source_url: str | None = None
    company_name: str | None = None
    match_score: float | None = None
    match_reason: str | None = None
    matched_skills: list[str] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobDetail(JobResponse):
    requirements: str | None = None
    posted_at: datetime | None = None


class JobSave(BaseModel):
    job_id: int
