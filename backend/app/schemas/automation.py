from datetime import datetime

from pydantic import BaseModel, Field


class AutomationStart(BaseModel):
    job_id: int
    job_url: str = Field(min_length=1, max_length=2000)


class AutomationConfirm(BaseModel):
    confirmed: bool = True


class AutomationResponse(BaseModel):
    id: int
    user_id: int
    job_id: int | None = None
    job_url: str | None = None
    status: str
    steps: str | None = None
    confirmation_required: bool
    user_confirmed: bool
    result: str | None = None
    screenshot_paths: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
