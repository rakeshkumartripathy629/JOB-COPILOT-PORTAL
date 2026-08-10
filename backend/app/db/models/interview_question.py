import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuestionCategory(str, enum.Enum):
    HR = "hr"
    TECHNICAL = "technical"
    JS = "js"
    REACT = "react"
    NODE = "node"
    PYTHON = "python"
    SQL = "sql"
    BEHAVIORAL = "behavioral"


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    category: Mapped[QuestionCategory] = mapped_column(SQLEnum(QuestionCategory), nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    suggested_answer: Mapped[str | None] = mapped_column(String, nullable=True)
    explanation: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="interview_questions")
    job = relationship("Job", back_populates="interview_questions")
