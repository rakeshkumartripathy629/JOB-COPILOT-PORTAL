"""Pydantic schemas for the career evidence system + advanced matching."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CareerFactStatusLiteral = Literal[
    "VERIFIED", "USER_CONFIRMED", "AI_EXTRACTED", "INFERRED", "UNKNOWN", "REJECTED"
]


class CareerFactOut(BaseModel):
    id: int
    user_id: int
    fact_type: str
    name: str
    value: str | None = None
    description: str | None = None
    confidence: int = 0
    status: str = "AI_EXTRACTED"
    verified_by_user: bool | None = False
    is_public: bool | None = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CareerEvidenceOut(BaseModel):
    id: int
    user_id: int
    career_fact_id: int
    evidence_type: str
    source: str
    source_id: int | None = None
    source_section: str | None = None
    evidence_text: str | None = None
    confidence: int = 0
    verification_status: str = "AI_EXTRACTED"
    verified_by_user: bool | None = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CareerFactUpdate(BaseModel):
    status: CareerFactStatusLiteral | None = None
    name: str | None = None
    value: str | None = None
    description: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    is_public: bool | None = None


class CareerEvidenceUpdate(BaseModel):
    verification_status: CareerFactStatusLiteral | None = None


class CareerVaultSummary(BaseModel):
    facts_total: int = 0
    facts_by_status: dict[str, int] = Field(default_factory=dict)
    facts_by_type: dict[str, int] = Field(default_factory=dict)
    evidence_total: int = 0


class RequirementMatrixItem(BaseModel):
    requirement_id: int
    requirement: str
    skill: str | None = None
    importance: str
    is_critical: bool = False
    classification: str
    fact_id: int | None = None
    fact_name: str | None = None
    skill_score: int = 0
    confidence: int = 0
    evidence_text: str | None = None


class MatchedFactOut(BaseModel):
    fact_id: int
    fact_name: str
    fact_type: str
    classification: str
    evidence_text: str | None = None
    confidence: int = 0


class AdvancedMatchOut(BaseModel):
    overall_score: int
    required_skill_score: int
    preferred_skill_score: int
    education_score: int
    career_goal_score: int
    experience_score: int
    seniority_score: int
    location_score: int
    salary_score: int
    responsibility_score: int
    match_confidence: int
    recommendation: str
    requirements: list[RequirementMatrixItem] = Field(default_factory=list)
    critical_missing: list[str] = Field(default_factory=list)
    matched_facts: list[MatchedFactOut] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)
    relevant_achievements: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    why_match: str = ""
    why_not: str = ""
    match_reason: str = ""


class ShouldApplyOut(BaseModel):
    decision: str
    confidence: int
    recommendation: str
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)


class RoiOut(BaseModel):
    roi_score: int
    decision: str
    estimated_salary: int | None = None
    salary_currency: str | None = "USD"
    salary_confidence: int = 0
    signals: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class JobEvidenceOut(BaseModel):
    id: int
    career_fact_id: int | None = None
    fact_name: str | None = None
    fact_type: str | None = None
    classification: str
    reason: str | None = None
    evidence_text: str | None = None
    confidence: int = 0
    created_at: datetime | None = None
