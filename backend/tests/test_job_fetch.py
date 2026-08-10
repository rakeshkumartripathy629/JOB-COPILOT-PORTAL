from sqlalchemy import select

from app.config import settings
from app.db.models.company import Company
from app.db.models.job import Job
from app.db.models.resume import Resume
from app.services.job_search_service import JobSearchService
from app.services.resume_job_service import build_queries, fetch_jobs_for_resume
from tests.helpers import create_resume, seed_job


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"status {self.status_code}")


class FakeClient:
    def __init__(self, *args, **kwargs):
        self._factory = None

    def set_factory(self, factory):
        self._factory = factory

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return self._factory()


async def _mock_http(monkeypatch, factory):
    import app.services.job_search_service as mod

    client = FakeClient()
    client.set_factory(factory)
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda *a, **k: client)


JSEARCH_PAYLOAD = {
    "data": [
        {
            "job_title": "Backend Developer",
            "job_city": "Bengaluru",
            "job_state": "Karnataka",
            "job_country": "India",
            "job_apply_link": "https://jsearch.example.com/1",
            "employer_name": "Acme India",
            "job_description": "Build REST APIs with Python and FastAPI.",
            "job_employment_type": "FULLTIME",
            "job_posted_at_datetime_utc": "2026-08-01T10:00:00Z",
        }
    ]
}


async def test_fetch_from_jsearch_sets_country(db, monkeypatch):
    monkeypatch.setattr(settings, "RAPIDAPI_KEY", "test-key")
    await _mock_http(monkeypatch, lambda: FakeResponse(200, JSEARCH_PAYLOAD))
    service = JobSearchService(db)
    created = await service.fetch_from_jsearch("backend developer", country="in")
    assert created == 1

    result = await db.execute(select(Job).where(Job.source == "jsearch"))
    job = result.scalar_one()
    assert job.title == "Backend Developer"
    assert job.country == "India"
    assert "Bengaluru" in job.location


async def test_fetch_from_jsearch_skips_without_key(db, monkeypatch):
    monkeypatch.setattr(settings, "RAPIDAPI_KEY", "")
    service = JobSearchService(db)
    assert await service.fetch_from_jsearch("backend developer") == 0


async def test_fetch_from_jsearch_skips_on_rejected(db, monkeypatch):
    monkeypatch.setattr(settings, "RAPIDAPI_KEY", "test-key")
    await _mock_http(monkeypatch, lambda: FakeResponse(403))
    service = JobSearchService(db)
    assert await service.fetch_from_jsearch("backend developer") == 0


GOOGLE_PAYLOAD = {
    "items": [
        {
            "title": "Backend Developer - Naukri.com",
            "link": "https://www.naukri.com/backend-developer-job",
            "snippet": "Backend developer job in Bangalore, India.",
        }
    ]
}


async def test_fetch_from_google_cse_skips_without_keys(db, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "")
    service = JobSearchService(db)
    assert await service.fetch_from_google_cse("backend developer") == 0


async def test_fetch_from_google_cse_upserts_india(db, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "test-cx")
    await _mock_http(monkeypatch, lambda: FakeResponse(200, GOOGLE_PAYLOAD))
    service = JobSearchService(db)
    created = await service.fetch_from_google_cse("backend developer")
    assert created == 1

    result = await db.execute(select(Job).where(Job.source == "google"))
    job = result.scalar_one()
    assert job.country == "India"
    assert job.source_url == "https://www.naukri.com/backend-developer-job"

    company = await db.execute(select(Company).where(Company.name == "naukri.com"))
    assert company.scalar_one()


def test_build_queries_uses_designation_and_skills():
    queries = build_queries({"designation": "Backend Developer", "skills": ["Python", "FastAPI", "SQL"]})
    assert queries == ["Backend Developer", "Backend Developer Python", "Backend Developer FastAPI"]


def test_build_queries_falls_back_to_defaults():
    queries = build_queries({})
    assert queries == ["software engineer", "backend developer", "data scientist"]


async def test_fetch_jobs_for_resume_respects_flag(db, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_RESUME_JOB_FETCH", False)
    user_id = 1
    resume_id = await create_resume(db, user_id, parsed_data='{"designation": "Backend Developer", "skills": ["Python"]}')
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one()

    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("fetch_india should not run when auto-fetch disabled")

    monkeypatch.setattr(JobSearchService, "fetch_india", should_not_be_called)
    result = await fetch_jobs_for_resume(db, resume)
    assert result == {"added": 0, "per_source": {}}


async def test_search_filters_by_country(db, client, auth_headers):
    india_id = await seed_job(db, title="Backend Engineer", company_name="Wipro", country="India")
    await seed_job(db, title="Backend Engineer", company_name="US Corp", country="United States")

    r = client.get("/jobs/search?country=India", headers=auth_headers())
    assert r.status_code == 200, r.text
    ids = [j["id"] for j in r.json()]
    assert india_id in ids
    assert all(j["country"] == "India" for j in r.json())


async def test_job_detail_includes_country(db, client, auth_headers):
    job_id = await seed_job(db, country="India")
    r = client.get(f"/jobs/{job_id}", headers=auth_headers())
    assert r.status_code == 200, r.text
    assert r.json()["country"] == "India"
