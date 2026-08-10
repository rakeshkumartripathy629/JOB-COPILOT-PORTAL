import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api import (
    admin,
    analytics,
    applications,
    auth,
    automation,
    career,
    cover_letters,
    interviews,
    jobs,
    notifications,
    resumes,
    users,
)
from app.config import settings
from app.core.logging_setup import setup_logging
from app.db import models  # noqa: F401  (registers all models on Base.metadata)
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.middleware.cors import cors_middleware
from app.middleware.error_handler import register_exception_handlers
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

setup_logging()

JOB_REFRESH_INTERVAL_SECONDS = 6 * 60 * 60


async def _job_refresh_loop() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                from app.services.live_jobs_service import refresh_jobs

                result = await refresh_jobs(db)
                logger.info("Background job refresh: %s", result)
        except Exception:
            logger.exception("Background job refresh failed")
        await asyncio.sleep(JOB_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured")
    if settings.ENABLE_BACKGROUND_JOB_REFRESH:
        asyncio.create_task(_job_refresh_loop())
    yield


app = FastAPI(
    title="AI Job Copilot",
    description="AI-powered job application assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please slow down."})


app.add_middleware(CORSMiddleware, **cors_middleware())
register_exception_handlers(app)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(career.router, prefix="/career", tags=["career"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(cover_letters.router, prefix="/cover-letters", tags=["cover-letters"])
app.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
app.include_router(automation.router, prefix="/automation", tags=["automation"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "error", "database": "disconnected"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
