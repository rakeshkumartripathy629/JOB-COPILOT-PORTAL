from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.automation import AutomationConfirm, AutomationResponse, AutomationStart
from app.services.automation_service import AutomationService

router = APIRouter()


@router.post("/start", response_model=AutomationResponse, status_code=201)
async def start_automation(
    data: AutomationStart,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AutomationService(db)
    session = await service.start_session(current_user.id, data.job_id, data.job_url)
    return AutomationResponse.model_validate(session)


@router.post("/{session_id}/analyze", response_model=AutomationResponse)
async def analyze_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.automation_session_repo import AutomationSessionRepository

    repo = AutomationSessionRepository(db)
    session = await repo.get(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    service = AutomationService(db)
    return AutomationResponse.model_validate(await service.analyze_page(session_id))


@router.get("/{session_id}", response_model=AutomationResponse)
async def get_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.automation_session_repo import AutomationSessionRepository

    repo = AutomationSessionRepository(db)
    session = await repo.get(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return AutomationResponse.model_validate(session)


@router.post("/{session_id}/confirm", response_model=AutomationResponse)
async def confirm_session(
    session_id: int,
    data: AutomationConfirm,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models.automation_session import AutomationStatus
    from app.repositories.automation_session_repo import AutomationSessionRepository

    repo = AutomationSessionRepository(db)
    session = await repo.get(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.user_confirmed = data.confirmed
    session.status = AutomationStatus.COMPLETED if data.confirmed else AutomationStatus.CANCELLED
    await repo.db.commit()
    await repo.db.refresh(session)
    return AutomationResponse.model_validate(session)


@router.post("/{session_id}/cancel", response_model=AutomationResponse)
async def cancel_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models.automation_session import AutomationStatus
    from app.repositories.automation_session_repo import AutomationSessionRepository

    repo = AutomationSessionRepository(db)
    session = await repo.get(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = AutomationStatus.CANCELLED
    await repo.db.commit()
    await repo.db.refresh(session)
    return AutomationResponse.model_validate(session)
