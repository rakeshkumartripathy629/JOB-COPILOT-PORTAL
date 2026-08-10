import asyncio
import logging
import os
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.resume_repo import ResumeRepository, ResumeVersionRepository
from app.services.matching_service import MatchingService
from app.tasks.resume_tasks import parse_resume_task

logger = logging.getLogger(__name__)

ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def detect_mime(content: bytes) -> str:
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content[:4] == b"PK\x03\x04":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


class ResumeService:
    def __init__(self, db: AsyncSession):
        self.resume_repo = ResumeRepository(db)
        self.version_repo = ResumeVersionRepository(db)
        self.matching_service = MatchingService(db)

    async def upload_resume(self, user_id: int, file: UploadFile, title: str):
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise ValueError(f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE} bytes.")
        mime = detect_mime(content)
        ext = ALLOWED_MIME.get(mime)
        if not ext:
            raise ValueError("Invalid file type. Only PDF and DOCX allowed.")

        filename = f"{uuid.uuid4()}{ext}"
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        path = os.path.join(settings.UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            f.write(content)

        resume = await self.resume_repo.create(
            {
                "user_id": user_id,
                "title": title,
                "file_path": path,
                "file_type": ext,
            }
        )
        try:
            parse_resume_task.delay(resume.id)
        except Exception as e:
            logger.warning("Broker unavailable (%s); parsing resume inline", e)
            await asyncio.to_thread(parse_resume_task, resume.id)
        from app.db.models.notification import NotificationType
        from app.services.notification_service import NotificationService

        await NotificationService(self.resume_repo.db).notify(
            user_id,
            NotificationType.SYSTEM,
            "Resume uploaded",
            f'Your resume "{title}" was uploaded and is being processed.',
        )
        return resume

    async def optimize_resume(self, resume_id: int, job_id: int):
        resume = await self.resume_repo.get(resume_id)
        if not resume:
            raise ValueError("Resume not found")
        match_result = await self.matching_service.match_job_for_resume(resume_id, job_id)
        version = await self.version_repo.create(
            {
                "resume_id": resume_id,
                "user_id": resume.user_id,
                "content": str(match_result),
                "version_label": f"Optimized for job {job_id}",
            }
        )
        return version
