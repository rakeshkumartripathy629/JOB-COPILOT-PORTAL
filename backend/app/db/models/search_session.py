from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SearchSession(Base):
    """A personalized resume-driven live job search session."""

    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    resume_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("resumes.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="SEARCHING", nullable=False, index=True)
    time_range: Mapped[str] = mapped_column(String(20), default="any", nullable=False)
    remote_filter: Mapped[str] = mapped_column(String(20), default="any", nullable=False)
    sources_requested: Mapped[str | None] = mapped_column(String(500), nullable=True)
    profile_json: Mapped[str | None] = mapped_column(String, nullable=True)
    queries_json: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="search_sessions")
    queries = relationship("SearchQuery", back_populates="session", cascade="all, delete-orphan")
    source_statuses = relationship("SearchSourceStatus", back_populates="session", cascade="all, delete-orphan")
    results = relationship("JobSearchResult", back_populates="session", cascade="all, delete-orphan")


class SearchQuery(Base):
    """A single search query executed during a search session."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_sessions.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    sources: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("SearchSession", back_populates="queries")


class SearchSourceStatus(Base):
    """Real, observable status of a single job source during a search session."""

    __tablename__ = "search_source_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_sessions.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    portal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("SearchSession", back_populates="source_statuses")
