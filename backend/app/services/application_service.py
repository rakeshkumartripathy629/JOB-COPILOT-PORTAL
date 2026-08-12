"""Application management + tracking + CRM service.

Everything in this module is persisted and scoped to the authenticated user. No fake
applications, no fake statuses, no fake analytics - all numbers are derived from real
rows in the database.

Document versions are frozen at creation time so an application always shows the exact
resume/cover-letter version that was used when it was created.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.application import (
    RESPONSE_STATUSES,
    TERMINAL_STATUSES,
    Application,
    ApplicationAuditEvent,
    ApplicationDocument,
    ApplicationDocumentType,
    ApplicationNote,
    ApplicationReminder,
    ApplicationSnapshot,
    ApplicationSource,
    ApplicationStatus,
    ApplicationStatusHistory,
    ApplicationTag,
    can_transition,
)
from app.db.models.company import Company
from app.db.models.cover_letter import CoverLetter
from app.db.models.job import Job
from app.db.models.notification import NotificationType
from app.db.models.resume import Resume
from app.db.models.resume_version import ResumeVersion
from app.db.models.user import User

FOLLOWUP_AFTER_DAYS = 7
SILENCE_AFTER_DAYS = 14

# Sorts supported by the list endpoint.
VALID_SORTS = {"newest", "oldest", "match_score", "priority", "company", "status"}


class ApplicationServiceError(Exception):
    """Base error for application domain failures."""


class ApplicationNotFoundError(ApplicationServiceError):
    pass


class DuplicateApplicationError(ApplicationServiceError):
    pass


class InvalidStatusTransitionError(ApplicationServiceError):
    pass


def _match_query_terms(value: str) -> str:
    return value.strip()


async def _create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str | None = None,
    scheduled_at: datetime | None = None,
):
    from app.db.models.notification import Notification

    notif = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        scheduled_at=scheduled_at,
    )
    db.add(notif)
    await db.commit()
    return notif


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_job(db: AsyncSession, job_id: int) -> tuple[Job, Company | None]:
    result = await db.execute(select(Job, Company).join(Company, Job.company_id == Company.id).where(Job.id == job_id))
    row = result.first()
    if not row:
        raise ApplicationNotFoundError("Job not found")
    return row[0], row[1]


async def _owned_application(db: AsyncSession, user_id: int, application_id: int) -> Application:
    result = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == user_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise ApplicationNotFoundError("Application not found")
    return app


async def _job_title(db: AsyncSession, job_id: int) -> str | None:
    result = await db.execute(select(Job.title).where(Job.id == job_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Creation (+ snapshot + frozen documents + duplicate protection)
# ---------------------------------------------------------------------------


async def create_application(
    db: AsyncSession,
    *,
    user_id: int,
    job_id: int,
    application_source: str = ApplicationSource.JOB_SEARCH.value,
    priority: str = "MEDIUM",
    status: str = ApplicationStatus.READY.value,
    resume_id: int | None = None,
    resume_version_id: int | None = None,
    tailored_resume_id: int | None = None,
    cover_letter_id: int | None = None,
    application_answer_version_id: int | None = None,
    application_packet_id: int | None = None,
    tags: list[str] | None = None,
) -> Application:
    """Create an application for a real job with a permanent snapshot + documents."""
    job, company = await _load_job(db, job_id)

    # --- duplicate protection -------------------------------------------------
    existing = await _find_duplicate(db, user_id, job)
    if existing:
        raise DuplicateApplicationError("An application for this job already exists")

    status = ApplicationStatus(status).value

    app = Application(
        user_id=user_id,
        job_id=job.id,
        status=status,
        application_source=application_source,
        priority=priority,
        resume_id=resume_id,
        resume_version_id=resume_version_id,
        tailored_resume_id=tailored_resume_id,
        cover_letter_id=cover_letter_id,
        cover_letter_version_id=cover_letter_id,
        application_answer_version_id=application_answer_version_id,
        application_packet_id=application_packet_id,
    )
    db.add(app)
    await db.flush()

    snapshot = ApplicationSnapshot(
        application_id=app.id,
        user_id=user_id,
        job_title=job.title,
        company_name=company.name if company else None,
        location=job.location,
        country=job.country,
        remote_type=job.job_type.value if job.job_type else None,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        description=job.description,
        requirements=job.requirements,
        responsibilities=job.responsibilities,
        source=job.source,
        source_url=job.source_url,
        application_url=job.application_url,
        canonical_url=job.canonical_url,
        source_job_id=job.source_job_id,
        posted_at=job.posted_at,
        match_score=None,
        match_confidence=None,
        job_quality_score=job.job_quality_score,
    )
    db.add(snapshot)

    # --- freeze document versions -------------------------------------------
    await _freeze_documents(
        db,
        user_id=user_id,
        application_id=app.id,
        resume_id=resume_id,
        resume_version_id=resume_version_id,
        tailored_resume_id=tailored_resume_id,
        cover_letter_id=cover_letter_id,
    )

    # --- history + audit -----------------------------------------------------
    db.add(
        ApplicationStatusHistory(
            application_id=app.id,
            user_id=user_id,
            old_status=None,
            new_status=status,
            source="system",
            reason="Application created from job",
        )
    )
    db.add(
        ApplicationAuditEvent(
            application_id=app.id,
            user_id=user_id,
            event="application.created",
            meta=json.dumps({"job_id": job.id, "job_title": job.title, "source": application_source}),
        )
    )

    if tags:
        for tag in {_match_query_terms(t) for t in tags if _match_query_terms(t)}:
            db.add(ApplicationTag(application_id=app.id, user_id=user_id, tag=tag))

    await db.commit()
    await db.refresh(app)
    return app


async def _find_duplicate(db: AsyncSession, user_id: int, job: Job) -> Application | None:
    # 1) Direct (user, job) duplicate.
    direct = (
        await db.execute(select(Application).where(Application.user_id == user_id, Application.job_id == job.id))
    ).scalar_one_or_none()
    if direct:
        return direct

    # 2) Same canonical job surfaced from a different source.
    if job.canonical_url:
        by_canonical = (
            await db.execute(
                select(Application)
                .join(Job, Application.job_id == Job.id)
                .where(Application.user_id == user_id, Job.canonical_url == job.canonical_url)
            )
        ).scalars().first()
        if by_canonical:
            return by_canonical

    # 3) Same source + source job id (board-specific id is unique per source).
    if job.source and job.source_job_id:
        by_source_id = (
            await db.execute(
                select(Application)
                .join(Job, Application.job_id == Job.id)
                .where(Application.user_id == user_id, Job.source == job.source, Job.source_job_id == job.source_job_id)
            )
        ).scalars().first()
        if by_source_id:
            return by_source_id

    return None


async def _freeze_documents(
    db: AsyncSession,
    *,
    user_id: int,
    application_id: int,
    resume_id: int | None,
    resume_version_id: int | None,
    tailored_resume_id: int | None,
    cover_letter_id: int | None,
) -> None:
    if resume_version_id:
        version = await db.get(ResumeVersion, resume_version_id)
        if version and version.user_id == user_id:
            resume = await db.get(Resume, version.resume_id)
            db.add(
                ApplicationDocument(
                    application_id=application_id,
                    user_id=user_id,
                    doc_type=ApplicationDocumentType.RESUME.value,
                    version_label=version.version_label or "current",
                    content_snippet=version.content,
                    storage_path=resume.file_path if resume else None,
                )
            )

    if tailored_resume_id:
        version = await db.get(ResumeVersion, tailored_resume_id)
        if version and version.user_id == user_id:
            db.add(
                ApplicationDocument(
                    application_id=application_id,
                    user_id=user_id,
                    doc_type=ApplicationDocumentType.TAILORED_RESUME.value,
                    version_label=version.version_label or "tailored",
                    content_snippet=version.content,
                )
            )

    if cover_letter_id:
        letter = await db.get(CoverLetter, cover_letter_id)
        if letter and letter.user_id == user_id:
            db.add(
                ApplicationDocument(
                    application_id=application_id,
                    user_id=user_id,
                    doc_type=ApplicationDocumentType.COVER_LETTER.value,
                    version_label=f"v{letter.id}",
                    content_snippet=letter.content,
                )
            )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def get_application(db: AsyncSession, user_id: int, application_id: int) -> Application:
    return await _owned_application(db, user_id, application_id)


async def list_applications(
    db: AsyncSession,
    user_id: int,
    *,
    status: str | None = None,
    company: str | None = None,
    location: str | None = None,
    remote: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_match_score: int | None = None,
    source: str | None = None,
    job_source: str | None = None,
    search: str | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Application], int, int]:
    stmt = (
        select(Application, Job.title.label("job_title"), Company.name.label("company_name"))
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(Application.user_id == user_id)
    )

    if status:
        stmt = stmt.where(Application.status == status.upper())
    if company:
        stmt = stmt.where(Company.name.ilike(f"%{company}%"))
    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if remote:
        stmt = stmt.where(Job.job_type == remote.upper())
    if date_from:
        stmt = stmt.where(Application.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Application.created_at <= date_to)
    if min_match_score is not None:
        stmt = stmt.where(Application.match_score >= min_match_score)
    if source:
        stmt = stmt.where(Application.application_source == source.upper())
    if job_source:
        stmt = stmt.where(Job.source == job_source)
    if search:
        term = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                Job.title.ilike(term),
                Company.name.ilike(term),
                Job.location.ilike(term),
                Application.notes.ilike(term),
                Application.id.in_(
                    select(ApplicationNote.application_id).where(
                        ApplicationNote.user_id == user_id, ApplicationNote.note.ilike(term)
                    )
                ),
                Application.id.in_(
                    select(ApplicationTag.application_id).where(
                        ApplicationTag.user_id == user_id, ApplicationTag.tag.ilike(term)
                    )
                ),
            )
        )


    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    sort_clauses: dict[str, Any] = {
        "newest": Application.created_at.desc(),
        "oldest": Application.created_at.asc(),
        "match_score": Application.match_score.desc().nullslast(),
        "priority": Application.priority.asc(),
        "company": Company.name.asc(),
        "status": Application.status.asc(),
    }
    order = sort_clauses.get(sort, sort_clauses["newest"])
    stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(stmt)).all()
    apps = [row[0] for row in rows]
    pages = (total + page_size - 1) // page_size if page_size else 1
    return apps, total, pages


async def update_application(
    db: AsyncSession,
    *,
    user_id: int,
    application_id: int,
    notes: str | None = None,
    priority: str | None = None,
) -> Application:
    app = await _owned_application(db, user_id, application_id)
    if notes is not None:
        app.notes = notes
    if priority is not None:
        app.priority = priority.upper()
    await db.commit()
    await db.refresh(app)
    return app


# ---------------------------------------------------------------------------
# Status transitions (validated + recorded + notified)
# ---------------------------------------------------------------------------


async def change_status(
    db: AsyncSession,
    *,
    user_id: int,
    application_id: int,
    new_status: str,
    reason: str | None = None,
    source: str = "user",
) -> tuple[Application, bool]:
    """Change an application's status. Returns (app, reopened) where reopened is
    True when the move left a terminal state (explicit reopening)."""
    app = await _owned_application(db, user_id, application_id)

    try:
        new_status_enum = ApplicationStatus(new_status.upper())
    except ValueError:
        raise InvalidStatusTransitionError(f"Unknown status: {new_status}") from None

    old_status_enum = ApplicationStatus(app.status)

    if old_status_enum == new_status_enum:
        return app, False

    reopened = old_status_enum in TERMINAL_STATUSES and new_status_enum not in TERMINAL_STATUSES
    if not can_transition(old_status_enum, new_status_enum):
        raise InvalidStatusTransitionError(
            f"Invalid transition: {old_status_enum.value} -> {new_status_enum.value}"
        )

    now = datetime.utcnow()
    app.status = new_status_enum.value

    # Track the first time the user actually submitted the application.
    if new_status_enum == ApplicationStatus.APPLIED and app.applied_at is None:
        app.applied_at = now

    # Track the first meaningful employer response.
    if new_status_enum in RESPONSE_STATUSES and app.responded_at is None:
        app.responded_at = now

    db.add(
        ApplicationStatusHistory(
            application_id=app.id,
            user_id=user_id,
            old_status=old_status_enum.value,
            new_status=new_status_enum.value,
            source=source,
            reason=reason,
            meta=json.dumps({"reopened": reopened}),
        )
    )
    db.add(
        ApplicationAuditEvent(
            application_id=app.id,
            user_id=user_id,
            event="application.status_changed",
            meta=json.dumps(
                {"from": old_status_enum.value, "to": new_status_enum.value, "reason": reason, "reopened": reopened}
            ),
        )
    )

    await db.commit()
    await db.refresh(app)

    title = await _job_title(db, app.job_id)
    await _create_notification(
        db,
        user_id=user_id,
        notification_type=NotificationType.STATUS_CHANGE,
        title="Application status updated",
        message=f"{title or 'Your application'} is now {new_status_enum.value}.",
    )
    return app, reopened


# ---------------------------------------------------------------------------
# Timeline / audit
# ---------------------------------------------------------------------------


async def get_timeline(db: AsyncSession, user_id: int, application_id: int) -> list[ApplicationStatusHistory]:
    await _owned_application(db, user_id, application_id)
    result = await db.execute(
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.changed_at.desc())
    )
    return list(result.scalars().all())


async def get_audit(db: AsyncSession, user_id: int, application_id: int) -> list[ApplicationAuditEvent]:
    await _owned_application(db, user_id, application_id)
    result = await db.execute(
        select(ApplicationAuditEvent)
        .where(ApplicationAuditEvent.application_id == application_id)
        .order_by(ApplicationAuditEvent.timestamp.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


async def add_note(db: AsyncSession, *, user_id: int, application_id: int, note: str) -> ApplicationNote:
    await _owned_application(db, user_id, application_id)
    row = ApplicationNote(application_id=application_id, user_id=user_id, note=note)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_notes(db: AsyncSession, user_id: int, application_id: int) -> list[ApplicationNote]:
    await _owned_application(db, user_id, application_id)
    result = await db.execute(
        select(ApplicationNote)
        .where(ApplicationNote.application_id == application_id)
        .order_by(ApplicationNote.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


async def add_tag(db: AsyncSession, *, user_id: int, application_id: int, tag: str) -> ApplicationTag:
    await _owned_application(db, user_id, application_id)
    tag = _match_query_terms(tag)
    existing = (
        await db.execute(
            select(ApplicationTag).where(
                ApplicationTag.application_id == application_id,
                ApplicationTag.user_id == user_id,
                ApplicationTag.tag == tag,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    row = ApplicationTag(application_id=application_id, user_id=user_id, tag=tag)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def remove_tag(db: AsyncSession, *, user_id: int, application_id: int, tag: str) -> None:
    await _owned_application(db, user_id, application_id)
    result = await db.execute(
        select(ApplicationTag).where(
            ApplicationTag.application_id == application_id,
            ApplicationTag.user_id == user_id,
            ApplicationTag.tag == tag,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()


async def list_tags(db: AsyncSession, user_id: int, application_id: int) -> list[str]:
    await _owned_application(db, user_id, application_id)
    result = await db.execute(
        select(ApplicationTag.tag)
        .where(ApplicationTag.application_id == application_id, ApplicationTag.user_id == user_id)
        .order_by(ApplicationTag.tag)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Follow-up recommendations (computed, user-initiated actions only)
# ---------------------------------------------------------------------------


def _build_followup_message(
    *,
    job_title: str,
    company_name: str | None,
    applied_at: datetime | None,
    user_name: str | None,
    mode: str = "professional",
) -> str:
    company = company_name or "your team"
    applied = applied_at.strftime("%d %b %Y") if applied_at else "recently"
    signoff = user_name or "a candidate"
    if mode == "short":
        return (
            f"Hi {company},\n\nI applied for the {job_title} position on {applied}. "
            f"I wanted to check on the status of my application and whether any further "
            f"information is needed from me.\n\nBest,\n{signoff}"
        )
    if mode == "friendly":
        return (
            f"Hi {company},\n\nHope you're doing well! I applied for the {job_title} role "
            f"on {applied} and I'm really excited about the opportunity. I just wanted to "
            f"touch base and see if there are any updates. Happy to provide anything else "
            f"you need.\n\nThanks,\n{signoff}"
        )
    return (
        f"Dear {company} Hiring Team,\n\nI submitted my application for the {job_title} "
        f"position on {applied} and wanted to follow up. I remain very interested in the "
        f"role and would welcome the opportunity to discuss my qualifications further.\n\n"
        f"Thank you for your time.\n\nBest regards,\n{signoff}"
    )


async def generate_followup(
    db: AsyncSession, *, user_id: int, application_id: int, mode: str = "professional"
) -> dict[str, Any]:
    """Recommend (never auto-send) a follow-up and produce a ready-to-send message."""
    app = await _owned_application(db, user_id, application_id)
    if mode not in ("professional", "short", "friendly"):
        mode = "professional"

    user = await db.get(User, user_id)
    job = await db.get(Job, app.job_id)
    company = await db.get(Company, job.company_id) if job and job.company_id else None

    recommended = False
    reason = None
    if app.applied_at is not None:
        days = (datetime.utcnow() - app.applied_at).days
        if app.responded_at is None and days >= FOLLOWUP_AFTER_DAYS:
            recommended = True
            reason = f"No response {days} days after applying (>{FOLLOWUP_AFTER_DAYS} days)."
        elif app.responded_at is None and days < FOLLOWUP_AFTER_DAYS:
            reason = f"Too early to follow up; application is {days} days old."
        else:
            reason = "Already received a response; a follow-up is not recommended."

    app.follow_up_recommended_at = datetime.utcnow()
    app.follow_up_reason = reason
    app.follow_up_status = "RECOMMENDED" if recommended else "NOT_RECOMMENDED"
    await db.commit()

    message = _build_followup_message(
        job_title=job.title if job else "the position",
        company_name=company.name if company else None,
        applied_at=app.applied_at,
        user_name=user.full_name if user else None,
        mode=mode,
    )
    return {
        "recommended": recommended,
        "reason": reason,
        "recommended_at": app.follow_up_recommended_at,
        "message": message,
        "mode": mode,
    }


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


async def create_reminder(
    db: AsyncSession,
    *,
    user_id: int,
    application_id: int,
    reminder_type: str,
    due_at: datetime,
) -> ApplicationReminder:
    await _owned_application(db, user_id, application_id)
    row = ApplicationReminder(
        application_id=application_id,
        user_id=user_id,
        reminder_type=reminder_type,
        due_at=due_at,
        status="PENDING",
    )
    db.add(row)
    await db.flush()

    # Create the user-facing notification immediately (scheduled for the due date).
    notif_type = NotificationType.INTERVIEW_REMINDER if reminder_type == "INTERVIEW" else NotificationType.FOLLOW_UP
    await _create_notification(
        db,
        user_id=user_id,
        notification_type=notif_type,
        title=f"Reminder set: {reminder_type.replace('_', ' ').title()}",
        message=f"Due {due_at.isoformat()}. You can manage this from the application timeline.",
        scheduled_at=due_at,
    )
    await db.refresh(row)
    return row


async def complete_reminder(db: AsyncSession, *, user_id: int, reminder_id: int) -> ApplicationReminder:
    result = await db.execute(
        select(ApplicationReminder).where(ApplicationReminder.id == reminder_id, ApplicationReminder.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApplicationNotFoundError("Reminder not found")
    row.status = "DONE"
    await db.commit()
    await db.refresh(row)
    return row


async def list_reminders(db: AsyncSession, user_id: int, *, pending_only: bool = False) -> list[ApplicationReminder]:
    stmt = select(ApplicationReminder).where(ApplicationReminder.user_id == user_id)
    if pending_only:
        stmt = stmt.where(ApplicationReminder.status == "PENDING")
    stmt = stmt.order_by(ApplicationReminder.due_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Analytics + performance (real data only, drafts never counted)
# ---------------------------------------------------------------------------


async def get_analytics(db: AsyncSession, user_id: int) -> dict[str, Any]:
    result = await db.execute(
        select(
            Application.id,
            Application.status,
            Application.applied_at,
            Application.responded_at,
        ).where(Application.user_id == user_id)
    )
    rows = result.all()

    submitted = [r for r in rows if r.applied_at is not None or r.status not in ("DRAFT", "READY")]
    applied_count = len(submitted)
    drafts = sum(1 for r in rows if r.status == "DRAFT")
    ready = sum(1 for r in rows if r.status == "READY")

    responses = [r for r in submitted if r.responded_at is not None or r.status in RESPONSE_STATUSES]
    interviews = [r for r in submitted if r.status in ("INTERVIEW", "TECHNICAL_ROUND", "FINAL_ROUND", "OFFER")]
    final_rounds = [r for r in submitted if r.status in ("FINAL_ROUND", "OFFER")]
    offers = [r for r in submitted if r.status == "OFFER"]
    rejected = sum(1 for r in submitted if r.status == "REJECTED")
    withdrawn = sum(1 for r in submitted if r.status == "WITHDRAWN")

    def rate(n: int) -> int:
        return round(n * 100 / applied_count) if applied_count else 0

    return {
        "total_applications": len(rows),
        "drafts": drafts,
        "ready": ready,
        "applied": applied_count,
        "responses": len(responses),
        "interviews": len(interviews),
        "final_rounds": len(final_rounds),
        "offers": len(offers),
        "rejected": rejected,
        "withdrawn": withdrawn,
        "response_rate": rate(len(responses)),
        "interview_rate": rate(len(interviews)),
        "offer_rate": rate(len(offers)),
        "funnel": {
            "applied": applied_count,
            "responses": len(responses),
            "interviews": len(interviews),
            "final_rounds": len(final_rounds),
            "offers": len(offers),
        },
    }


async def get_performance(db: AsyncSession, user_id: int) -> dict[str, Any]:
    """Best-performing breakdowns; suppresses thin groups (n < 3)."""
    result = await db.execute(
        select(
            Application.status,
            Application.applied_at,
            Application.responded_at,
            Job.title.label("job_title"),
            Company.name.label("company_name"),
            Job.location.label("location"),
            Job.source.label("job_source"),
            Application.application_source.label("app_source"),
        )
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(
            Application.user_id == user_id,
            or_(Application.applied_at.isnot(None), Application.status.notin_(("DRAFT", "READY"))),
        )
    )
    rows = result.all()

    def group(rows, keyfn):
        groups: dict[str, list] = {}
        for r in rows:
            key = keyfn(r)
            if not key:
                continue
            groups.setdefault(key, []).append(r)
        out = []
        for key, items in groups.items():
            entry = {
                "key": key,
                "applications": len(items),
                "responses": sum(1 for r in items if r.responded_at is not None or r.status in RESPONSE_STATUSES),
                "interviews": sum(1 for r in items if r.status in ("INTERVIEW", "TECHNICAL_ROUND", "FINAL_ROUND", "OFFER")),
                "offers": sum(1 for r in items if r.status == "OFFER"),
            }
            n = entry["applications"]
            if n < 3:
                entry["notice"] = "Not enough data (fewer than 3 applications)."
            else:
                entry["response_rate"] = round(entry["responses"] * 100 / n)
                entry["interview_rate"] = round(entry["interviews"] * 100 / n)
                entry["offer_rate"] = round(entry["offers"] * 100 / n)
            out.append(entry)
        return sorted(out, key=lambda e: -e["applications"])

    return {
        "by_company": group(rows, lambda r: r.company_name),
        "by_role": group(rows, lambda r: r.job_title),
        "by_location": group(rows, lambda r: r.location),
        "by_job_source": group(rows, lambda r: r.job_source),
        "by_application_source": group(rows, lambda r: r.app_source),
    }


async def needs_attention(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    """Actionable follow-up / interview / assessment items (real records only)."""
    now = datetime.utcnow()
    items: list[dict[str, Any]] = []

    # Follow-ups due: applied, no response, and past the follow-up window.
    result = await db.execute(
        select(Application, Job.title, Company.name)
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(
            Application.user_id == user_id,
            Application.status.in_(("APPLIED", "VIEWED")),
            Application.applied_at.isnot(None),
            Application.applied_at <= now - timedelta(days=FOLLOWUP_AFTER_DAYS),
            Application.responded_at.is_(None),
        )
    )
    for app, title, company in result.all():
        items.append(
            {
                "kind": "FOLLOW_UP",
                "application_id": app.id,
                "job_title": title,
                "company_name": company,
                "reason": f"No response {FOLLOWUP_AFTER_DAYS}+ days after applying.",
                "due_at": app.applied_at + timedelta(days=FOLLOWUP_AFTER_DAYS),
            }
        )

    # Pending reminders that are due or coming up soon.
    soon = now + timedelta(days=3)
    result = await db.execute(
        select(ApplicationReminder, Job.title, Company.name)
        .join(Application, ApplicationReminder.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(
            ApplicationReminder.user_id == user_id,
            ApplicationReminder.status == "PENDING",
            ApplicationReminder.due_at <= soon,
        )
    )
    for reminder, title, company in result.all():
        items.append(
            {
                "kind": "REMINDER",
                "application_id": reminder.application_id,
                "reminder_id": reminder.id,
                "reminder_type": reminder.reminder_type,
                "job_title": title,
                "company_name": company,
                "reason": f"Reminder {reminder.reminder_type.replace('_', ' ').title()} is due.",
                "due_at": reminder.due_at,
            }
        )

    return sorted(items, key=lambda i: (i.get("due_at") or now).timestamp())


# ---------------------------------------------------------------------------
# Documents (frozen versions + signed download URLs)
# ---------------------------------------------------------------------------


def _sign(doc_id: int, user_id: int, application_id: int) -> str:
    expiry = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
    payload = f"{user_id}:{application_id}:{doc_id}:{expiry}"
    sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_signature(token: str, doc_id: int, user_id: int, application_id: int) -> bool:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        payload, sig = parts
        expected = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        _, _, _, expiry = payload.split(":")
        return int(expiry) >= int(datetime.utcnow().timestamp())
    except (ValueError, TypeError):
        return False


async def list_documents(
    db: AsyncSession, user_id: int, application_id: int
) -> list[dict[str, Any]]:
    await _owned_application(db, user_id, application_id)
    result = await db.execute(
        select(ApplicationDocument).where(
            ApplicationDocument.application_id == application_id, ApplicationDocument.user_id == user_id
        )
    )
    docs = list(result.scalars().all())
    return [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "version_label": d.version_label,
            "download_url": f"/applications/{application_id}/documents/{d.id}/download?token={_sign(d.id, user_id, application_id)}",
        }
        for d in docs
    ]


async def get_document_payload(
    db: AsyncSession, user_id: int, application_id: int, document_id: int
) -> tuple[ApplicationDocument, bytes | str | None]:
    result = await db.execute(
        select(ApplicationDocument).where(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise ApplicationNotFoundError("Document not found")
    payload: bytes | str | None = None
    if doc.doc_type in (ApplicationDocumentType.RESUME.value, ApplicationDocumentType.TAILORED_RESUME.value):
        if doc.storage_path:
            import os

            if os.path.exists(doc.storage_path):
                with open(doc.storage_path, "rb") as f:
                    payload = f.read()
        if payload is None:
            payload = doc.content_snippet
    else:
        payload = doc.content_snippet
    return doc, payload


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def export_csv(db: AsyncSession, user_id: int) -> str:
    stmt = (
        select(Application, Job.title.label("job_title"), Company.name.label("company_name"))
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "job_id",
            "job_title",
            "company",
            "status",
            "source",
            "priority",
            "applied_at",
            "responded_at",
            "match_score",
            "notes",
            "tags",
            "created_at",
        ]
    )
    ids = [r[0].id for r in rows]
    tag_map: dict[int, list[str]] = {}
    if ids:
        result = await db.execute(select(ApplicationTag).where(ApplicationTag.application_id.in_(ids)))
        for t in result.scalars().all():
            tag_map.setdefault(t.application_id, []).append(t.tag)

    for app, job_title, company_name in rows:
        writer.writerow(
            [
                app.id,
                app.job_id,
                job_title,
                company_name,
                app.status,
                app.application_source,
                app.priority,
                app.applied_at.isoformat() if app.applied_at else "",
                app.responded_at.isoformat() if app.responded_at else "",
                app.match_score,
                app.notes,
                ",".join(tag_map.get(app.id, [])),
                app.created_at.isoformat() if app.created_at else "",
            ]
        )
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def delete_application(db: AsyncSession, user_id: int, application_id: int) -> None:
    """Permanently delete an application and all of its CRM rows."""
    app = await _owned_application(db, user_id, application_id)

    related_tables = (
        ApplicationSnapshot,
        ApplicationStatusHistory,
        ApplicationNote,
        ApplicationTag,
        ApplicationReminder,
        ApplicationAuditEvent,
        ApplicationDocument,
    )
    for model in related_tables:
        await db.execute(delete(model).where(model.application_id == application_id))
    await db.delete(app)
    await db.commit()
