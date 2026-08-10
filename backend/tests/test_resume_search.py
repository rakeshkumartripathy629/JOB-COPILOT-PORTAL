"""Tests for the resume-driven live job search flow (backend)."""

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.db.models.company import Company
from app.db.models.job import Job
from app.db.models.profile import Profile
from app.db.models.user import User
from app.services.job_sources import registry
from app.services.job_sources.base import JobSource, NormalizedJob, SourceResult, SourceStatus
from app.services.live_search_service import run_search_task, start_search
from tests.helpers import create_resume


def make_job(
    title="Backend Engineer",
    company="Acme Corp",
    url="https://acme.com/jobs/1",
    source="FakePortal",
    posted_at=None,
    remote_type="remote",
):
    now = datetime.utcnow()
    return NormalizedJob(
        title=title,
        company=company,
        source=source,
        search_source="fake",
        description="Backend engineer building REST APIs with Node.js, Express, PostgreSQL, Docker and AWS.",
        location="Bangalore",
        country="India",
        remote_type=remote_type,
        salary_min=2000,
        salary_max=4000,
        salary_currency="USD",
        posted_at=posted_at,
        discovered_at=now,
        last_verified_at=now,
        source_job_id=url,
        source_url=url,
        canonical_url=url,
        application_url=url,
    )


class FakeSource(JobSource):
    name = "fake"
    display_name = "Fake Portal"
    portal = "FakePortal"

    def __init__(self, jobs, name="fake", display_name="Fake Portal", portal="FakePortal"):
        self.name = name
        self.display_name = display_name
        self.portal = portal
        self._jobs = jobs

    async def search(self, query, profile=None):
        return SourceResult(SourceStatus.SUCCESS, jobs=list(self._jobs))


@pytest.fixture
def fake_sources():
    saved = registry.all()
    registry.clear()
    created = []

    def _use(list_of_job_lists):
        registry.clear()
        created.clear()
        for i, jobs in enumerate(list_of_job_lists):
            source = FakeSource(jobs, name=f"fake{i}", display_name=f"FakePortal{i}", portal=f"FakePortal{i}")
            created.append(source)
            registry.register(source)
        return created

    yield _use
    registry.clear()
    for source in saved:
        registry.register(source)


async def _get_user(db, email="test@example.com") -> User:
    return (await db.execute(select(User).where(User.email == email))).scalar_one()


def _wait_for_status(client, headers, search_id, timeout=15.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/jobs/search/{search_id}/status", headers=headers)
        assert r.status_code == 200, r.text
        status = r.json()["status"]
        if status in ("COMPLETED", "FAILED"):
            return status
        time.sleep(0.2)
    raise AssertionError(f"search {search_id} did not finish within {timeout}s")

async def _seed_resume(db, user_id: int):
    await create_resume(
        db,
        user_id,
        parsed_data=json.dumps(
            {
                "designation": "Backend Developer",
                "skills": ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"],
                "experience": [
                    "2021 - Present: Backend Developer at Acme",
                    "2020 - 2021: Junior Developer at Beta",
                ],
                "summary": "Backend developer with Node.js, PostgreSQL and AWS.",
            }
        ),
    )
    db.add(Profile(user_id=user_id, location="India"))
    await db.commit()


async def test_search_gated_without_resume(client, auth_headers):
    headers = auth_headers()
    r = client.post("/jobs/search", json={"time_range": "any"}, headers=headers)
    assert r.status_code == 400
    assert "resume" in r.json()["detail"].lower()

    r = client.get("/jobs/profile", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"has_resume": False, "profile": None}


async def test_search_runs_with_unparsed_resume(db, client, auth_headers, fake_sources):
    fake_sources([[make_job()]])
    headers = auth_headers()
    user = await _get_user(db)
    await create_resume(db, user.id, parsed_data="")

    r = client.get("/jobs/profile", headers=headers)
    assert r.status_code == 200
    assert r.json()["has_resume"] is True

    r = client.post("/jobs/search", json={"time_range": "any", "sources": ["fake0"]}, headers=headers)
    assert r.status_code == 200, r.text
    search_id = r.json()["search_id"]

    assert _wait_for_status(client, headers, search_id) == "COMPLETED"
    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["jobs"]) == 1


async def test_search_reuses_existing_jobs_when_multiple_match(
    db, client, auth_headers, fake_sources
):
    fake_sources([[make_job()]])
    headers = auth_headers()
    user = await _get_user(db)
    await _seed_resume(db, user.id)

    company = Company(name="Acme Corp")
    db.add(company)
    await db.flush()

    job1 = Job(
        company_id=company.id,
        title="Backend Engineer",
        dedupe_key="backend engineer|acme corp",
        source_url="https://acme.com/jobs/1",
        canonical_url="https://acme.com/jobs/1",
        source="legacy",
    )
    job2 = Job(
        company_id=company.id,
        title="Legacy Duplicate",
        dedupe_key="legacy duplicate|acme corp",
        source_url="https://acme.com/jobs/1",
        canonical_url="https://acme.com/jobs/1",
        source="legacy",
    )
    db.add_all([job1, job2])
    await db.commit()

    r = client.post("/jobs/search", json={"time_range": "any", "sources": ["fake0"]}, headers=headers)
    assert r.status_code == 200, r.text
    search_id = r.json()["search_id"]

    assert _wait_for_status(client, headers, search_id) == "COMPLETED"
    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["id"] in {job1.id, job2.id}


async def test_profile_with_resume(db, client, auth_headers):
    headers = auth_headers()
    user = await _get_user(db)
    await _seed_resume(db, user.id)
    r = client.get("/jobs/profile", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["has_resume"] is True
    assert "Backend Developer" in data["profile"]["roles"]
    assert "Node.js" in data["profile"]["skills"]
    assert data["profile"]["experienceYears"] is not None


async def test_full_pipeline_dedupe_and_rank(db, client, auth_headers, fake_sources):
    fake_sources(
        [
            [
                make_job(source="FakePortal0"),
                make_job(title="Frontend Engineer", url="https://acme.com/frontend", remote_type="onsite", source="FakePortal0"),
            ],
            [
                make_job(source="FakePortal1", url="https://fake1.example/acme-backend"),
                make_job(title="Backend Engineer", company="Beta Inc", url="https://beta.com/backend"),
            ],
        ]
    )
    headers = auth_headers()
    user = await _get_user(db)
    await _seed_resume(db, user.id)

    r = client.post(
        "/jobs/search",
        json={"time_range": "any", "remote": "any", "sources": ["fake0", "fake1"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    search_id = r.json()["search_id"]

    status = _wait_for_status(client, headers, search_id)
    assert status == "COMPLETED"

    r = client.get(f"/jobs/search/{search_id}/status", headers=headers)
    assert r.json()["status"] == "COMPLETED"

    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "COMPLETED"
    jobs = data["jobs"]
    assert len(jobs) == 3

    backend = [j for j in jobs if j["title"] == "Backend Engineer" and j["company_name"] == "Acme Corp"]
    assert len(backend) == 1
    assert set(backend[0]["sources"]) == {"FakePortal0", "FakePortal1"}

    for j in jobs:
        assert j["match_score"] is not None
        assert j["skill_score"] is not None

    assert sorted(j["rank"] for j in jobs) == list(range(1, len(jobs) + 1))


async def test_remote_and_time_filters(db, client, auth_headers, fake_sources):
    fake_sources(
        [
            [
                make_job(),
                make_job(title="Frontend Engineer", url="https://acme.com/frontend", remote_type="onsite"),
                make_job(
                    title="DevOps Engineer",
                    company="Beta Inc",
                    url="https://beta.com/devops",
                    posted_at=datetime.utcnow(),
                ),
            ]
        ]
    )
    headers = auth_headers()
    user = await _get_user(db)
    await _seed_resume(db, user.id)

    r = client.post("/jobs/search", json={"time_range": "any", "remote": "remote", "sources": ["fake0"]}, headers=headers)
    search_id = r.json()["search_id"]
    assert _wait_for_status(client, headers, search_id) == "COMPLETED"

    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    jobs = r.json()["jobs"]
    assert all(j["remote_type"] == "remote" for j in jobs)
    assert all("onsite" not in (j["remote_type"] or "") for j in jobs)

    # "Last 1 hour" excludes jobs without a verified posting time.
    r = client.get(f"/jobs/search/{search_id}?time_range=1h", headers=headers)
    filtered = r.json()["jobs"]
    assert all(j["posting_verified"] for j in filtered)
    assert all(j["title"] != "Backend Engineer" for j in filtered)  # unverified posting time


async def test_history_and_delete(db, client, auth_headers, fake_sources):
    fake_sources([[make_job()]])
    headers = auth_headers()
    user = await _get_user(db)
    await _seed_resume(db, user.id)

    search_id = await start_search(db, user_id=user.id, time_range="any", remote="any", sources=["fake0"])
    await run_search_task(search_id)

    r = client.get("/jobs/searches", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "COMPLETED"

    r = client.delete(f"/jobs/search/{search_id}", headers=headers)
    assert r.status_code == 200

    r = client.get("/jobs/searches", headers=headers)
    assert r.json() == []


async def test_other_users_cannot_access_session(db, client, auth_headers, fake_sources):
    fake_sources([[make_job()]])
    auth_headers()
    user = await _get_user(db)
    await _seed_resume(db, user.id)
    search_id = await start_search(db, user_id=user.id, time_range="any", remote="any", sources=["fake0"])
    await run_search_task(search_id)

    other = auth_headers("other@example.com", "Password123!")
    r = client.get(f"/jobs/search/{search_id}/status", headers=other)
    assert r.status_code == 404
    r = client.get(f"/jobs/search/{search_id}", headers=other)
    assert r.status_code == 404
