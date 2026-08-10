import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CoverLetterStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    resume_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("resumes.id"), nullable=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[CoverLetterStatus] = mapped_column(
        SQLEnum(CoverLetterStatus), default=CoverLetterStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="cover_letters")
    job = relationship("Job", back_populates="cover_letters")
    resume = relationship("Resume", back_populates="cover_letters")
