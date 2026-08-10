import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AutomationStatus(str, enum.Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationSession(Base):
    __tablename__ = "automation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    job_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[AutomationStatus] = mapped_column(
        SQLEnum(AutomationStatus), default=AutomationStatus.STARTED, nullable=False
    )
    steps: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmation_required: Mapped[bool | None] = mapped_column(Boolean, default=True)
    user_confirmed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    result: Mapped[str | None] = mapped_column(String, nullable=True)
    screenshot_paths: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="automation_sessions")
    job = relationship("Job", back_populates="automation_sessions")
