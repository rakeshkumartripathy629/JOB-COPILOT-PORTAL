"""Pydantic schemas for the resume-driven live job search flow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TimeRange = Literal["1h", "24h", "3d", "7d", "any"]
RemoteFilter = Literal["any", "remote", "hybrid", "onsite"]


class SearchStartRequest(BaseModel):
    time_range: TimeRange = "7d"
    remote: RemoteFilter = "any"
    sources: list[str] | None = None


class SearchStartResponse(BaseModel):
    search_id: int
    status: str = "SEARCHING"


class SearchProfileResponse(BaseModel):
    has_resume: bool
    profile: dict | None = None


class SourceStatusItem(BaseModel):
    name: str
    portal: str | None = None
    status: str
    count: int = 0
    error: str | None = None


class SearchSessionStatusResponse(BaseModel):
    search_id: int
    status: str
    time_range: str | None = None
    remote: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    queries: list[str] = Field(default_factory=list)
    sources: list[SourceStatusItem] = Field(default_factory=list)


class JobSearchResultCard(BaseModel):
    id: int
    search_result_id: int | None = None
    rank: int | None = None
    title: str
    company_name: str | None = None
    location: str | None = None
    country: str | None = None
    job_type: str | None = None
    remote_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str | None = None
    skills_required: str | None = None
    seniority: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    posted_at: datetime | None = None
    posting_verified: bool | None = None
    discovered_at: datetime | None = None
    last_verified_at: datetime | None = None
    freshness: str | None = None
    is_active: bool | None = None
    source: str | None = None
    search_source: str | None = None
    source_url: str | None = None
    canonical_url: str | None = None
    application_url: str | None = None
    sources: list[str] = Field(default_factory=list)
    source_references: list[dict] = Field(default_factory=list)
    match_score: int | None = None
    skill_score: int | None = None
    experience_score: int | None = None
    responsibility_score: int | None = None
    seniority_score: int | None = None
    location_score: int | None = None
    salary_score: int | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    match_reason: str | None = None
    job_quality_score: int | None = None
    rank_explanation: str | None = None
    match_confidence: int | None = None
    requirements: dict | None = None
    evidence_count: int | None = None


class SearchResultsResponse(BaseModel):
    search_id: int
    status: str
    message: str | None = None
    jobs: list[JobSearchResultCard] = Field(default_factory=list)


class SearchHistoryItem(BaseModel):
    search_id: int
    status: str
    time_range: str | None = None
    remote: str | None = None
    queries: list[str] = Field(default_factory=list)
    result_count: int = 0
    created_at: datetime | None = None
    completed_at: datetime | None = None
