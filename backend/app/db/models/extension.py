"""Chrome Extension support: application sessions, fill logs, and event logs.

These tables back the Smart Autofill extension. They only store what is needed to
operate the extension and audit its actions. Sensitive field *values* are never
persisted server-side: fill logs store counts, not content.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExtensionSessionStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    READY = "READY"
    FILLING = "FILLING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FILLED = "FILLED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class ExtensionSession(Base):
    """A user's browser-side application session, mirrored for audit/support."""

    __tablename__ = "extension_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    page_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ats: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ExtensionSessionStatus] = mapped_column(
        SQLEnum(ExtensionSessionStatus), default=ExtensionSessionStatus.DETECTED, nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="extension_sessions")


class ExtensionFillLog(Base):
    """Aggregate fill statistics for a session. Counts only, never field values."""

    __tablename__ = "extension_fill_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fields_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fields_filled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fields_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fields_reviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fields_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="extension_fill_logs")


class ExtensionLog(Base):
    """Non-sensitive extension event log (level + event + message)."""

    __tablename__ = "extension_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(10), default="info", nullable=False)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="extension_logs")
