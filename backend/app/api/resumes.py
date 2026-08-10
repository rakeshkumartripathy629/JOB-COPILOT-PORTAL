import contextlib
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.resume import ResumeDetail, ResumeResponse, ResumeVersionResponse
from app.services.resume_service import ResumeService

router = APIRouter()


@router.post("/upload", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    try:
        resume = await service.upload_resume(current_user.id, file, title)
        return ResumeResponse.model_validate(resume)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.resume_repo import ResumeRepository

    repo = ResumeRepository(db)
    resumes = await repo.get_by_user(current_user.id)
    return [ResumeResponse.model_validate(r) for r in resumes]


@router.get("/{resume_id}", response_model=ResumeDetail)
async def get_resume(
    resume_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.resume_repo import ResumeRepository

    repo = ResumeRepository(db)
    resume = await repo.get(resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Resume not found")
    return ResumeDetail.model_validate(resume)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.resume_repo import ResumeRepository

    repo = ResumeRepository(db)
    resume = await repo.get(resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Resume not found")
    file_path = resume.file_path
    await repo.delete(resume_id)
    if file_path and os.path.exists(file_path):
        with contextlib.suppress(OSError):
            os.remove(file_path)
    return None


@router.post("/{resume_id}/optimize", response_model=ResumeVersionResponse)
async def optimize_resume(
    resume_id: int,
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeService(db)
    try:
        version = await service.optimize_resume(resume_id, job_id)
        return ResumeVersionResponse.model_validate(version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
