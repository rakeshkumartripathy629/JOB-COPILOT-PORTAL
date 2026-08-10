"""Career Vault API: career facts + evidence management (per-user)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.career import CareerEvidence, CareerFact
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.career import (
    CareerEvidenceOut,
    CareerEvidenceUpdate,
    CareerFactOut,
    CareerFactUpdate,
    CareerVaultSummary,
)
from app.services.career_evidence_service import (
    get_career_evidence,
    get_career_facts,
    rebuild_career_vault,
    update_career_evidence,
    update_career_fact,
)

router = APIRouter()


@router.get("/facts", response_model=list[CareerFactOut])
async def list_career_facts(
    status: str | None = Query(default=None),
    fact_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    facts = await get_career_facts(db, current_user.id, status=status, fact_type=fact_type, limit=limit)
    return facts


@router.get("/evidence", response_model=list[CareerEvidenceOut])
async def list_career_evidence(
    fact_id: int | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if fact_id is not None:
        fact = (
            await db.execute(
                select(CareerFact).where(CareerFact.id == fact_id, CareerFact.user_id == current_user.id)
            )
        ).scalar_one_or_none()
        if fact is None:
            raise HTTPException(status_code=404, detail="Career fact not found")
    return await get_career_evidence(db, current_user.id, fact_id=fact_id, limit=limit)


@router.patch("/facts/{fact_id}", response_model=CareerFactOut)
async def patch_career_fact(
    fact_id: int,
    body: CareerFactUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        fact = await update_career_fact(
            db,
            current_user.id,
            fact_id,
            status=body.status,
            name=body.name,
            value=body.value,
            description=body.description,
            confidence=body.confidence,
            is_public=body.is_public,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if fact is None:
        raise HTTPException(status_code=404, detail="Career fact not found")
    return fact


@router.patch("/evidence/{evidence_id}", response_model=CareerEvidenceOut)
async def patch_career_evidence(
    evidence_id: int,
    body: CareerEvidenceUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        evidence = await update_career_evidence(
            db, current_user.id, evidence_id, verification_status=body.verification_status
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return evidence


@router.post("/index")
async def index_career_vault(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """(Re)build career facts + evidence from the latest resume. Idempotent."""
    try:
        return await rebuild_career_vault(db, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/summary", response_model=CareerVaultSummary)
async def career_vault_summary(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    facts = (
        (await db.execute(select(CareerFact).where(CareerFact.user_id == current_user.id)))
        .scalars()
        .all()
    )
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for f in facts:
        by_status[f.status] = by_status.get(f.status, 0) + 1
        by_type[f.fact_type] = by_type.get(f.fact_type, 0) + 1
    evidence_total = (
        await db.execute(
            select(func.count(CareerEvidence.id)).where(CareerEvidence.user_id == current_user.id)
        )
    ).scalar_one()
    return CareerVaultSummary(
        facts_total=len(facts),
        facts_by_status=by_status,
        facts_by_type=by_type,
        evidence_total=evidence_total or 0,
    )
