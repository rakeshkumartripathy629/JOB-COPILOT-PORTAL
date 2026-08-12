from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobSourceReference(Base):
    """One listing occurrence of a canonical Job on a specific portal/source."""

    __tablename__ = "job_source_references"
    __table_args__ = (
        # Unique index on the combination a source uses to identify a listing.
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    search_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_portal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_at_precision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="source_references")
