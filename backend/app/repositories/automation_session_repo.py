from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.automation_session import AutomationSession
from app.repositories.base import BaseRepository


class AutomationSessionRepository(BaseRepository[AutomationSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(AutomationSession, db)
