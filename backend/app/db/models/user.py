from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    cover_letters = relationship("CoverLetter", back_populates="user", cascade="all, delete-orphan")
    interview_questions = relationship("InterviewQuestion", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    ai_logs = relationship("AiLog", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    automation_sessions = relationship("AutomationSession", back_populates="user", cascade="all, delete-orphan")
    search_sessions = relationship("SearchSession", back_populates="user", cascade="all, delete-orphan")
    career_facts = relationship("CareerFact", back_populates="user", cascade="all, delete-orphan")
    career_evidence = relationship("CareerEvidence", back_populates="user", cascade="all, delete-orphan")
    requirement_matches = relationship("JobRequirementMatch", back_populates="user", cascade="all, delete-orphan")
    match_evidence = relationship("JobMatchEvidence", back_populates="user", cascade="all, delete-orphan")
    extension_sessions = relationship("ExtensionSession", back_populates="user", cascade="all, delete-orphan")
    extension_fill_logs = relationship("ExtensionFillLog", back_populates="user", cascade="all, delete-orphan")
    extension_logs = relationship("ExtensionLog", back_populates="user", cascade="all, delete-orphan")


user_skills = Table(
    "user_skills",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id"), primary_key=True),
    Column("proficiency_level", String(50), nullable=False),
    Column("years_experience", Integer, nullable=True),
)
