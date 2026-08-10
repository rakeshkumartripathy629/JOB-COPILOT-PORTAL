import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobType(str, enum.Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    job_type: Mapped[JobType | None] = mapped_column(SQLEnum(JobType), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="USD")
    experience_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    experience_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    skills_required: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    search_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    remote_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True, index=True)
    posting_verified: Mapped[bool | None] = mapped_column(Boolean, default=False)
    freshness: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    job_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job")
    cover_letters = relationship("CoverLetter", back_populates="job")
    interview_questions = relationship("InterviewQuestion", back_populates="job")
    automation_sessions = relationship("AutomationSession", back_populates="job")
    source_references = relationship("JobSourceReference", back_populates="job", cascade="all, delete-orphan")
    search_results = relationship("JobSearchResult", back_populates="job", cascade="all, delete-orphan")
    job_requirement_rows = relationship("JobRequirement", back_populates="job", cascade="all, delete-orphan")
    requirement_matches = relationship("JobRequirementMatch", back_populates="job", cascade="all, delete-orphan")
    match_evidence = relationship("JobMatchEvidence", back_populates="job", cascade="all, delete-orphan")
