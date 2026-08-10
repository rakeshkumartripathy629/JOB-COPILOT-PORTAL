from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class ProfileBase(BaseModel):
    phone: str | None = None
    location: str | None = None
    headline: str | None = Field(None, max_length=255)
    summary: str | None = Field(None, max_length=2000)
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    website: HttpUrl | None = None


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserWithProfile(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    profile: ProfileResponse | None = None
    created_at: datetime

    class Config:
        from_attributes = True
