from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cover_letter import CoverLetterStatus
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.cover_letter import CoverLetterCreate, CoverLetterResponse, CoverLetterUpdate
from app.services.cover_letter_service import CoverLetterService

router = APIRouter()


@router.get("/", response_model=list[CoverLetterResponse])
async def list_cover_letters(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.cover_letter_repo import CoverLetterRepository

    repo = CoverLetterRepository(db)
    letters = await repo.get_by_user(current_user.id)
    return [CoverLetterResponse.model_validate(letter) for letter in letters]


@router.post("/", response_model=CoverLetterResponse, status_code=201)
async def create_cover_letter(
    data: CoverLetterCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CoverLetterService(db)
    letter = await service.generate_cover_letter(current_user.id, data.job_id, data.resume_id)
    return CoverLetterResponse.model_validate(letter)


@router.get("/{letter_id}", response_model=CoverLetterResponse)
async def get_cover_letter(
    letter_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.cover_letter_repo import CoverLetterRepository

    repo = CoverLetterRepository(db)
    letter = await repo.get(letter_id)
    if not letter or letter.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return CoverLetterResponse.model_validate(letter)


@router.patch("/{letter_id}", response_model=CoverLetterResponse)
async def update_cover_letter(
    letter_id: int,
    data: CoverLetterUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.cover_letter_repo import CoverLetterRepository

    repo = CoverLetterRepository(db)
    letter = await repo.get(letter_id)
    if not letter or letter.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    update_data: dict = {}
    if data.content is not None:
        update_data["content"] = data.content
    if data.status is not None:
        try:
            update_data["status"] = CoverLetterStatus(data.status)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status") from None
    letter = await repo.update(letter_id, update_data)
    return CoverLetterResponse.model_validate(letter)


@router.delete("/{letter_id}", status_code=204)
async def delete_cover_letter(
    letter_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.cover_letter_repo import CoverLetterRepository

    repo = CoverLetterRepository(db)
    letter = await repo.get(letter_id)
    if not letter or letter.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    await repo.delete(letter_id)
    return None
