import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{os.path.join(tempfile.gettempdir(), 'test_jobcopilot.db')}"
os.environ["OPENAI_API_KEY"] = ""
os.environ["UPLOAD_DIR"] = os.path.join(tempfile.gettempdir(), "test_uploads")
os.environ["ENABLE_BACKGROUND_JOB_REFRESH"] = "false"
os.environ["ENABLE_RESUME_JOB_FETCH"] = "false"
os.environ["RAPIDAPI_KEY"] = ""
os.environ["ADZUNA_APP_ID"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["GOOGLE_CSE_ID"] = ""

import pytest
from fastapi.testclient import TestClient

import app.db.models  # noqa: F401  (register all tables on Base.metadata)
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting():
    app.state.limiter.enabled = False
    yield


@pytest.fixture(autouse=True)
async def reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def auth_headers(client):
    def _make(email="test@example.com", password="Password123!"):
        r = client.post(
            "/auth/signup",
            json={"email": email, "password": password, "full_name": "Test User"},
        )
        if r.status_code == 400:
            pass
        else:
            assert r.status_code == 201, r.text
        r = client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
