import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ApplicationStatus(str, enum.Enum):
    """Canonical pipeline statuses (uppercase, stored as strings)."""

    DRAFT = "DRAFT"
    READY = "READY"
    APPLIED = "APPLIED"
    VIEWED = "VIEWED"
    RECRUITER_CONTACT = "RECRUITER_CONTACT"
    ASSESSMENT = "ASSESSMENT"
    INTERVIEW = "INTERVIEW"
    TECHNICAL_ROUND = "TECHNICAL_ROUND"
    FINAL_ROUND = "FINAL_ROUND"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ApplicationSource(str, enum.Enum):
    JOB_SEARCH = "JOB_SEARCH"
    SAVED_JOB = "SAVED_JOB"
    RECOMMENDATION = "RECOMMENDATION"
    MANUAL = "MANUAL"
    EXTENSION = "EXTENSION"  # reserved: automated workflow extensions
    AUTO_APPLY = "AUTO_APPLY"  # reserved: fully automated apply


class ApplicationPriority(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


TERMINAL_STATUSES = {
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.EXPIRED,
    ApplicationStatus.FAILED,
}

# Statuses that represent a meaningful employer response (used for response-rate math).
RESPONSE_STATUSES = {
    ApplicationStatus.VIEWED,
    ApplicationStatus.RECRUITER_CONTACT,
    ApplicationStatus.ASSESSMENT,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.TECHNICAL_ROUND,
    ApplicationStatus.FINAL_ROUND,
    ApplicationStatus.OFFER,
}

STAGE_ORDER = [
    ApplicationStatus.DRAFT,
    ApplicationStatus.READY,
    ApplicationStatus.APPLIED,
    ApplicationStatus.VIEWED,
    ApplicationStatus.RECRUITER_CONTACT,
    ApplicationStatus.ASSESSMENT,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.TECHNICAL_ROUND,
    ApplicationStatus.FINAL_ROUND,
    ApplicationStatus.OFFER,
]


def can_transition(old: ApplicationStatus, new: ApplicationStatus) -> bool:
    """Validate a status transition.

    Rules:
    - same status is a no-op (callers handle it).
    - from a terminal status the only valid move is reopening to DRAFT or READY
      (explicit reopening, recorded as such).
    - UNKNOWN may move to any status and any status may move to UNKNOWN.
    - otherwise any move to another non-terminal status is allowed (forward or
      backward); terminal statuses are always reachable from any non-terminal one.
    """
    if old == new:
        return False
    if old is ApplicationStatus.UNKNOWN or new is ApplicationStatus.UNKNOWN:
        return True
    if old in TERMINAL_STATUSES:
        return new in (ApplicationStatus.DRAFT, ApplicationStatus.READY)
    if new in TERMINAL_STATUSES:
        return True
    return True


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(30), default=ApplicationStatus.DRAFT.value, nullable=False, index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Where the application came from.
    application_source: Mapped[str] = mapped_column(
        String(30), default=ApplicationSource.JOB_SEARCH.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(String(10), default=ApplicationPriority.MEDIUM.value, nullable=False)
    ai_priority: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Document versions frozen at creation time (never re-pointed afterwards).
    resume_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("resumes.id"), nullable=True)
    resume_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("resume_versions.id"), nullable=True)
    tailored_resume_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_letter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cover_letters.id"), nullable=True)
    cover_letter_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_answer_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_packet_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Match context captured at creation time.
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Legacy free-form note column (kept for compatibility); structured notes live
    # in the application_notes table.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Follow-up recommendation (computed, not sent automatically).
    follow_up_recommended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    follow_up_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    follow_up_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    snapshot = relationship(
        "ApplicationSnapshot", back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    status_history = relationship(
        "ApplicationStatusHistory", back_populates="application", cascade="all, delete-orphan"
    )
    note_rows = relationship("ApplicationNote", back_populates="application", cascade="all, delete-orphan")
    tag_rows = relationship("ApplicationTag", back_populates="application", cascade="all, delete-orphan")
    reminders = relationship("ApplicationReminder", back_populates="application", cascade="all, delete-orphan")
    audit_events = relationship("ApplicationAuditEvent", back_populates="application", cascade="all, delete-orphan")
    documents = relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")


class ApplicationSnapshot(Base):
    """Immutable copy of the job + match at the moment the application was created."""

    __tablename__ = "application_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="snapshot")


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    application = relationship("Application", back_populates="status_history")


class ApplicationNote(Base):
    __tablename__ = "application_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("Application", back_populates="note_rows")


class ApplicationTag(Base):
    __tablename__ = "application_tags"
    __table_args__ = (
        UniqueConstraint("user_id", "application_id", "tag", name="uq_application_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="tag_rows")


class ApplicationReminder(Base):
    __tablename__ = "application_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(50), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="reminders")


class ApplicationAuditEvent(Base):
    __tablename__ = "application_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)

    application = relationship("Application", back_populates="audit_events")


class ApplicationDocumentType(str, enum.Enum):
    RESUME = "RESUME"
    COVER_LETTER = "COVER_LETTER"
    TAILORED_RESUME = "TAILORED_RESUME"
    ANSWERS = "ANSWERS"
    PACKET = "PACKET"


class ApplicationDocument(Base):
    """Document metadata frozen to the application at creation time."""

    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="documents")
