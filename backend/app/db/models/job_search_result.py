from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobSearchResult(Base):
    """A matched, ranked job result produced for a user's search session."""

    __tablename__ = "job_search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_sessions.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skill_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    experience_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    responsibility_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seniority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    salary_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_skills: Mapped[str | None] = mapped_column(String, nullable=True)
    missing_skills: Mapped[str | None] = mapped_column(String, nullable=True)
    related_skills: Mapped[str | None] = mapped_column(String, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rank_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirements_met: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirements_related: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirements_partial: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirements_missing: Mapped[int | None] = mapped_column(Integer, nullable=True)
    critical_missing: Mapped[str | None] = mapped_column(String, nullable=True)
    advanced_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("SearchSession", back_populates="results")
    job = relationship("Job", back_populates="search_results")
