from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.db.models.application import ApplicationSnapshot
from app.db.models.job import Job
from app.db.models.company import Company
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationResponse,
    ApplicationUpdate,
    ApplicationSnapshotOut,
    FollowUpRequest,
    NoteCreate,
    ReminderCreate,
    StatusUpdate,
    TagCreate,
)
from app.services import application_service as svc
from app.services.application_service import (
    ApplicationNotFoundError,
    ApplicationServiceError,
    DuplicateApplicationError,
    InvalidStatusTransitionError,
)

router = APIRouter()


def _to_response(app, job_title: str | None = None, company_name: str | None = None) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        user_id=app.user_id,
        job_id=app.job_id,
        status=app.status,
        applied_at=app.applied_at,
        responded_at=app.responded_at,
        application_source=app.application_source,
        priority=app.priority,
        ai_priority=app.ai_priority,
        resume_id=app.resume_id,
        resume_version_id=app.resume_version_id,
        tailored_resume_id=app.tailored_resume_id,
        cover_letter_id=app.cover_letter_id,
        cover_letter_version_id=app.cover_letter_version_id,
        application_answer_version_id=app.application_answer_version_id,
        application_packet_id=app.application_packet_id,
        notes=app.notes,
        follow_up_recommended_at=app.follow_up_recommended_at,
        follow_up_reason=app.follow_up_reason,
        follow_up_status=app.follow_up_status,
        job_title=job_title,
        company_name=company_name,
        match_score=app.match_score,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


async def _job_context(db: AsyncSession, job_id: int) -> tuple[str | None, str | None]:
    result = await db.execute(select(Job, Company).join(Company, Job.company_id == Company.id).where(Job.id == job_id))
    row = result.first()
    if not row:
        return None, None
    return row[0].title, row[1].name


def _handle_service_error(exc: ApplicationServiceError) -> HTTPException:
    if isinstance(exc, DuplicateApplicationError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, InvalidStatusTransitionError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, ApplicationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# List / create / get / update
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ApplicationResponse])
async def list_applications(
    status: str | None = None,
    company: str | None = None,
    location: str | None = None,
    remote: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_match_score: int | None = None,
    source: str | None = None,
    job_source: str | None = None,
    search: str | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime

    def _dt(value: str | None):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date format") from None

    apps, _, _ = await svc.list_applications(
        db,
        current_user.id,
        status=status,
        company=company,
        location=location,
        remote=remote,
        date_from=_dt(date_from),
        date_to=_dt(date_to),
        min_match_score=min_match_score,
        source=source,
        job_source=job_source,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    result = []
    for a in apps:
        title, company_name = await _job_context(db, a.job_id)
        result.append(_to_response(a, title, company_name))
    return result


@router.post("/", response_model=ApplicationResponse, status_code=201)
async def create_application(
    data: ApplicationCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        app = await svc.create_application(
            db,
            user_id=current_user.id,
            job_id=data.job_id,
            application_source=data.application_source or "JOB_SEARCH",
            priority=data.priority or "MEDIUM",
            resume_id=data.resume_id,
            resume_version_id=data.resume_version_id,
            tailored_resume_id=data.tailored_resume_id,
            cover_letter_id=data.cover_letter_id,
            application_answer_version_id=data.application_answer_version_id,
            application_packet_id=data.application_packet_id,
            tags=data.tags,
        )
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    title, company_name = await _job_context(db, app.job_id)
    return _to_response(app, title, company_name)


@router.get("/analytics", response_model=dict)
async def application_analytics(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.get_analytics(db, current_user.id)


@router.get("/performance", response_model=dict)
async def application_performance(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.get_performance(db, current_user.id)


@router.get("/needs-attention", response_model=list[dict])
async def needs_attention(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.needs_attention(db, current_user.id)


@router.get("/reminders", response_model=list[dict])
async def list_reminders(
    pending_only: bool = False,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_reminders(db, current_user.id, pending_only=pending_only)
    return [
        {
            "id": r.id,
            "application_id": r.application_id,
            "reminder_type": r.reminder_type,
            "due_at": r.due_at,
            "status": r.status,
            "title": r.title,
            "message": r.message,
        }
        for r in rows
    ]


@router.get("/export.csv")
async def export_csv(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await svc.export_csv(db, current_user.id)
    return PlainTextResponse(content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=applications.csv"})


@router.get("/{app_id}", response_model=ApplicationDetailResponse)
async def get_application(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        app = await svc.get_application(db, current_user.id, app_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc

    title, company_name = await _job_context(db, app.job_id)
    result = await db.execute(select(ApplicationSnapshot).where(ApplicationSnapshot.application_id == app.id))
    snapshot = result.scalar_one_or_none()
    tags = await svc.list_tags(db, current_user.id, app.id)
    documents = await svc.list_documents(db, current_user.id, app.id)
    timeline_rows = await svc.get_timeline(db, current_user.id, app.id)
    timeline = [
        {
            "old_status": t.old_status,
            "new_status": t.new_status,
            "source": t.source,
            "reason": t.reason,
            "changed_at": t.changed_at,
        }
        for t in timeline_rows
    ]

    base = _to_response(app, title, company_name)
    return ApplicationDetailResponse(
        **base.model_dump(),
        snapshot=ApplicationSnapshotOut.model_validate(snapshot) if snapshot else None,
        tags=tags,
        documents=documents,
        timeline=timeline,
    )


@router.patch("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: int,
    data: ApplicationUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        app = await svc.update_application(
            db, user_id=current_user.id, application_id=app_id, notes=data.notes, priority=data.priority
        )
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    title, company_name = await _job_context(db, app.job_id)
    return _to_response(app, title, company_name)


@router.post("/{app_id}/status", response_model=ApplicationResponse)
async def change_status(
    app_id: int,
    data: StatusUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        app, reopened = await svc.change_status(
            db, user_id=current_user.id, application_id=app_id, new_status=data.status, reason=data.reason
        )
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    title, company_name = await _job_context(db, app.job_id)
    return _to_response(app, title, company_name)


@router.get("/{app_id}/timeline", response_model=list[dict])
async def application_timeline(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = await svc.get_timeline(db, current_user.id, app_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return [
        {"old_status": r.old_status, "new_status": r.new_status, "source": r.source, "reason": r.reason, "changed_at": r.changed_at}
        for r in rows
    ]


@router.get("/{app_id}/audit", response_model=list[dict])
async def application_audit(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = await svc.get_audit(db, current_user.id, app_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return [{"event": r.event, "timestamp": r.timestamp, "metadata": r.meta} for r in rows]


@router.post("/{app_id}/notes", response_model=dict, status_code=201)
async def add_note(
    app_id: int,
    data: NoteCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.add_note(db, user_id=current_user.id, application_id=app_id, note=data.note)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return {"id": row.id, "note": row.note, "created_at": row.created_at}


@router.get("/{app_id}/notes", response_model=list[dict])
async def list_notes(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = await svc.list_notes(db, current_user.id, app_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return [{"id": r.id, "note": r.note, "created_at": r.created_at} for r in rows]


@router.post("/{app_id}/tags", response_model=dict, status_code=201)
async def add_tag(
    app_id: int,
    data: TagCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.add_tag(db, user_id=current_user.id, application_id=app_id, tag=data.tag)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return {"id": row.id, "tag": row.tag}


@router.get("/{app_id}/tags", response_model=list[str])
async def list_tags(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.list_tags(db, current_user.id, app_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.delete("/{app_id}/tags/{tag}")
async def remove_tag(
    app_id: int,
    tag: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.remove_tag(db, user_id=current_user.id, application_id=app_id, tag=tag)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return {"ok": True}


@router.post("/{app_id}/follow-up", response_model=dict)
async def generate_followup(
    app_id: int,
    data: FollowUpRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc.generate_followup(db, user_id=current_user.id, application_id=app_id, mode=data.mode)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return result


@router.post("/{app_id}/reminders", response_model=dict, status_code=201)
async def create_reminder(
    app_id: int,
    data: ReminderCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.create_reminder(
            db, user_id=current_user.id, application_id=app_id, reminder_type=data.reminder_type, due_at=data.due_at
        )
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return {"id": row.id, "reminder_type": row.reminder_type, "due_at": row.due_at, "status": row.status}


@router.post("/reminders/{reminder_id}/complete", response_model=dict)
async def complete_reminder(
    reminder_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.complete_reminder(db, user_id=current_user.id, reminder_id=reminder_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc
    return {"id": row.id, "status": row.status}


@router.get("/{app_id}/documents", response_model=list[dict])
async def list_documents(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.list_documents(db, current_user.id, app_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.get("/{app_id}/documents/{document_id}/download")
async def download_document(
    app_id: int,
    document_id: int,
    token: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not svc.verify_signature(token, document_id, current_user.id, app_id):
        raise HTTPException(status_code=403, detail="Invalid or expired download link")
    try:
        doc, payload = await svc.get_document_payload(db, current_user.id, app_id, document_id)
    except ApplicationServiceError as exc:
        raise _handle_service_error(exc) from exc

    if payload is None:
        raise HTTPException(status_code=404, detail="Document content is unavailable")
    filename = f"application-{app_id}-{doc.doc_type.lower()}.txt"
    if isinstance(payload, bytes):
        return StreamingResponse(
            iter([payload]),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    return PlainTextResponse(payload, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.delete("/{app_id}", status_code=204)
async def delete_application(
    app_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services import application_service

    try:
        await application_service.delete_application(db, current_user.id, app_id)
    except application_service.ApplicationNotFoundError:
        raise HTTPException(status_code=404, detail="Application not found")
