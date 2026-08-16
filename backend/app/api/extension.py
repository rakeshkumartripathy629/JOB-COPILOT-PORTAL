"""Chrome Extension Smart Autofill API.

All endpoints require the authenticated user and are strictly user-scoped. Inputs are
validated; page content sent by the extension is treated as untrusted data.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.extension import (
    AnalyzeFieldsOut,
    AnalyzeFieldsRequest,
    AnswerOut,
    ApplicationPacketOut,
    DetectAtsOut,
    DetectAtsRequest,
    DetectJobRequest,
    DetectedJobOut,
    ExtensionLogCreate,
    ExtensionLogOut,
    ExtensionSessionCreate,
    ExtensionSessionOut,
    FillLogCreate,
    FillLogOut,
    GenerateAnswerRequest,
    ValidateAnswerOut,
    ValidateAnswerRequest,
)
from app.services import extension_service

router = APIRouter()


@router.post("/session", response_model=ExtensionSessionOut)
async def create_session(
    body: ExtensionSessionCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.create_or_update_session(
        db, current_user.id, body.model_dump()
    )


@router.get("/career-profile")
async def career_profile(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.get_career_profile(db, current_user.id)


@router.post("/detect-job", response_model=DetectedJobOut)
async def detect_job(
    body: DetectJobRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.detect_job(db, current_user.id, body.model_dump())


@router.post("/detect-ats", response_model=DetectAtsOut)
async def detect_ats(
    body: DetectAtsRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.detect_ats(db, current_user.id, body.model_dump())


@router.post("/analyze-fields", response_model=AnalyzeFieldsOut)
async def analyze_fields(
    body: AnalyzeFieldsRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.analyze_fields(
        db, current_user.id, body.session_id, [f.model_dump() for f in body.fields],
        body.job.model_dump() if body.job else None,
    )


@router.get("/application-packet/{job_id}", response_model=ApplicationPacketOut)
async def application_packet(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await extension_service.get_application_packet(db, current_user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate-answer", response_model=AnswerOut)
async def generate_answer(
    body: GenerateAnswerRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.generate_answer(
        db,
        current_user.id,
        body.question,
        body.job_id,
        body.job.model_dump() if body.job else None,
        body.max_length,
    )


@router.post("/validate-answer", response_model=ValidateAnswerOut)
async def validate_answer(
    body: ValidateAnswerRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.validate_answer(db, current_user.id, body.answer)


@router.post("/fill-session", response_model=FillLogOut)
async def record_fill_log(
    body: FillLogCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.record_fill_log(db, current_user.id, body.model_dump())


@router.post("/log", response_model=ExtensionLogOut)
async def record_log(
    body: ExtensionLogCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await extension_service.record_log(db, current_user.id, body.model_dump())
