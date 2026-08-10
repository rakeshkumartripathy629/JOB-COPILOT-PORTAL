import asyncio

from app.db.base import Base
from app.db.models import (  # noqa: F401  (register all models on Base.metadata)
    activity_log,
    ai_log,
    application,
    automation_session,
    company,
    cover_letter,
    interview_question,
    job,
    notification,
    profile,
    refresh_token,
    resume,
    resume_version,
    skill,
    user,
)
from app.db.session import engine


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized")


asyncio.run(init())
