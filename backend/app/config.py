from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./jobcopilot.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_BEAT_BACKEND: str = "redis://localhost:6379/3"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    RAPIDAPI_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10485760
    RATE_LIMIT_PER_MINUTE: int = 60
    EMAIL_SENDER: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_HOST: str = ""
    EMAIL_PORT: int = 587
    SENDGRID_API_KEY: str = ""
    ENABLE_BACKGROUND_JOB_REFRESH: bool = True
    ENABLE_RESUME_JOB_FETCH: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
