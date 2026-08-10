"""Career evidence system: user career facts, evidence, and job requirement matches.

Career Vault = CareerFact + CareerEvidence. Every fact shown to the user is grounded in
evidence (resume section, user-stated skills, or explicit user confirmation). Job
requirement matches link a user's career facts to extracted job requirements.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CareerFactType(str, enum.Enum):
    TECHNICAL_SKILL = "technical_skill"
    SOFT_SKILL = "soft_skill"
    EXPERIENCE = "experience"
    JOB_TITLE = "job_title"
    RESPONSIBILITY = "responsibility"
    PROJECT = "project"
    ACHIEVEMENT = "achievement"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    TOOL = "tool"
    ROLE = "role"
    OTHER = "other"


class CareerFactStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    USER_CONFIRMED = "USER_CONFIRMED"
    AI_EXTRACTED = "AI_EXTRACTED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class EvidenceType(str, enum.Enum):
    RESUME_SECTION = "resume_section"
    RESUME_EXPERIENCE = "resume_experience"
    RESUME_PROJECT = "resume_project"
    RESUME_ACHIEVEMENT = "resume_achievement"
    RESUME_EDUCATION = "resume_education"
    RESUME_CERTIFICATION = "resume_certification"
    USER_SKILLS = "user_skills"
    JOB = "job"
    MANUAL = "manual"


class RequirementImportance(str, enum.Enum):
    REQUIRED = "REQUIRED"
    PREFERRED = "PREFERRED"
    NICE_TO_HAVE = "NICE_TO_HAVE"
    UNKNOWN = "UNKNOWN"


class RequirementClassification(str, enum.Enum):
    DIRECT_MATCH = "DIRECT_MATCH"
    RELATED_MATCH = "RELATED_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NO_EVIDENCE = "NO_EVIDENCE"


class CareerFact(Base):
    """A single verifiable statement about the user's career.

    Status reflects how strongly the fact is backed by evidence: VERIFIED and
    USER_CONFIRMED are human-approved; AI_EXTRACTED comes straight from the parsed
    resume; INFERRED/UNKNOWN are weaker derivations; REJECTED means the user
    explicitly dismissed it and it must never be used in matching.
    """

    __tablename__ = "career_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=CareerFactStatus.AI_EXTRACTED.value, nullable=False, index=True)
    verified_by_user: Mapped[bool | None] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="career_facts")
    evidence = relationship("CareerEvidence", back_populates="fact", cascade="all, delete-orphan")


class CareerEvidence(Base):
    """A single piece of evidence backing a career fact."""

    __tablename__ = "career_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    career_fact_id: Mapped[int] = mapped_column(Integer, ForeignKey("career_facts.id"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(30), default=CareerFactStatus.AI_EXTRACTED.value, nullable=False, index=True
    )
    verified_by_user: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="career_evidence")
    fact = relationship("CareerFact", back_populates="evidence")


class JobRequirement(Base):
    """A requirement extracted from a job posting's title/description/requirements."""

    __tablename__ = "job_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    requirement: Mapped[str] = mapped_column(String(500), nullable=False)
    skill: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    importance: Mapped[str] = mapped_column(String(30), default=RequirementImportance.UNKNOWN.value, nullable=False)
    is_critical: Mapped[bool | None] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="job_requirement_rows")
    matches = relationship("JobRequirementMatch", back_populates="requirement", cascade="all, delete-orphan")


class JobRequirementMatch(Base):
    """How a user's career fact matches a job requirement."""

    __tablename__ = "job_requirement_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    requirement_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_requirements.id"), nullable=False, index=True)
    career_fact_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("career_facts.id"), nullable=True, index=True)
    fact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification: Mapped[str] = mapped_column(
        String(30), default=RequirementClassification.NO_EVIDENCE.value, nullable=False
    )
    skill_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="requirement_matches")
    user = relationship("User", back_populates="requirement_matches")
    requirement = relationship("JobRequirement", back_populates="matches")
    career_fact = relationship("CareerFact")


class JobMatchEvidence(Base):
    """Top-level evidence surfaced for a job's match: why it matches / why not."""

    __tablename__ = "job_match_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    career_fact_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("career_facts.id"), nullable=True, index=True)
    fact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fact_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="match_evidence")
    user = relationship("User", back_populates="match_evidence")
    career_fact = relationship("CareerFact")
