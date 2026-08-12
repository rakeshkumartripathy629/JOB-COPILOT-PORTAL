"""Tests for dedicated portal adapters and job-source metadata (sourceMethod/precision)."""

import pytest

from app.config import settings
from app.services.job_sources import registry
from app.services.job_sources.base import SourceMethod, SourceStatus
from app.services.job_sources.http import SourceHTTPClient
from app.services.job_sources.instahyre import InstahyreJobSource
from app.services.job_sources.linkedin import LinkedInJobSource
from app.services.job_sources.naukri import NaukriJobSource
from app.services.job_sources.wellfound import WellfoundJobSource
from tests.test_resume_search import FakeSource


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


def _items(urls):
    items = []
    for i, url in enumerate(urls):
        items.append(
            {
                "title": f"Backend Engineer {i}",
                "link": url,
                "snippet": "Backend engineer with Node.js, PostgreSQL and Docker.",
            }
        )
    return items


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _make_fake_get(items):
    captured = {}

    async def fake_get(self, url, *, params=None, headers=None):
        captured["query"] = (params or {}).get("q", "")
        captured["num"] = (params or {}).get("num", None)
        return _FakeResponse(200, {"items": items})

    return fake_get, captured


def test_portal_adapters_registered():
    names = {s.name for s in registry.all()}
    assert {"linkedin", "wellfound", "instahyre", "naukri"} <= names


def test_portal_adapter_metadata():
    linkedin = LinkedInJobSource()
    assert linkedin.portal == "LinkedIn"
    assert linkedin.source_method == SourceMethod.PUBLIC_SEARCH_DISCOVERY
    assert linkedin.is_available() is False


async def test_portal_adapter_reports_unavailable_without_keys(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "")
    for source in (LinkedInJobSource(), WellfoundJobSource(), InstahyreJobSource(), NaukriJobSource()):
        result = await source.search("backend engineer")
        assert result.status == SourceStatus.UNAVAILABLE
        assert "not configured" in (result.error or "")


@pytest.mark.parametrize(
    "source_cls,url",
    [
        (LinkedInJobSource, "https://www.linkedin.com/jobs/view/12345"),
        (WellfoundJobSource, "https://wellfound.com/jobs/67890"),
        (InstahyreJobSource, "https://www.instahyre.com/job/54321"),
        (NaukriJobSource, "https://www.naukri.com/job-listings/backend-engineer-98765"),
    ],
)
async def test_portal_adapter_normalizes_real_cse_items(monkeypatch, source_cls, url):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "test-cx")
    fake_get, captured = _make_fake_get(_items([url]))
    monkeypatch.setattr(SourceHTTPClient, "get", fake_get)

    source = source_cls()
    result = await source.search("backend engineer")

    assert result.status == SourceStatus.SUCCESS
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.source == source.portal
    assert job.source_portal == source.portal
    assert job.source_method == SourceMethod.PUBLIC_SEARCH_DISCOVERY
    assert job.posted_at is None
    assert job.search_source == source.name
    assert source.site_operator in captured["query"]
    assert captured["num"] == source.num_results


async def test_portal_adapter_http_errors(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GOOGLE_CSE_ID", "test-cx")

    async def fake_403(self, url, *, params=None, headers=None):
        return _FakeResponse(403)

    monkeypatch.setattr(SourceHTTPClient, "get", fake_403)
    result = await LinkedInJobSource().search("backend engineer")
    assert result.status == SourceStatus.UNAVAILABLE
    assert result.count == 0


async def test_sources_status_endpoint(client, auth_headers):
    headers = auth_headers()
    r = client.get("/jobs/sources/status", headers=headers)
    assert r.status_code == 200
    data = r.json()
    by_name = {s["name"]: s for s in data["sources"]}
    for name in ("linkedin", "wellfound", "instahyre", "naukri", "google_cse"):
        assert name in by_name, by_name.keys()
        assert by_name[name]["source_method"] == "PUBLIC_SEARCH_DISCOVERY"
        assert by_name[name]["available"] is False
        assert by_name[name]["requires_config"] is not None


async def test_refresh_search_session(db, client, auth_headers, fake_sources):
    from app.services.live_search_service import run_search_task, start_search
    from tests.test_resume_search import _seed_resume, make_job

    fake_sources([[make_job(), make_job(title="Frontend Engineer", url="https://acme.com/fe")]])
    headers = auth_headers()
    user = (await _get_first_user(db))
    await _seed_resume(db, user.id)

    search_id = await start_search(db, user_id=user.id, time_range="any", remote="any", sources=["fake0"])
    await run_search_task(search_id)

    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    assert len(r.json()["jobs"]) == 2

    # Fake source now returns fewer jobs; refresh must re-run the search.
    fake_sources([[make_job()]])
    r = client.post(f"/jobs/search/{search_id}/refresh", headers=headers)
    assert r.status_code == 200
    assert r.json()["search_id"] == search_id

    import time

    deadline = time.time() + 15
    while time.time() < deadline:
        status = client.get(f"/jobs/search/{search_id}/status", headers=headers).json()["status"]
        if status in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    jobs = r.json()["jobs"]
    assert len(jobs) == 1, jobs


async def test_source_method_and_precision_propagate(db, client, auth_headers, fake_sources):
    from datetime import datetime

    from tests.test_resume_search import _seed_resume, make_job

    now = datetime.utcnow()
    verified = make_job(title="Verified Role", url="https://acme.com/verified")
    verified.posted_at = now
    verified.source_method = SourceMethod.AUTHORIZED_FEED
    unverified = make_job(title="Unverified Role", url="https://acme.com/unverified")
    unverified.posted_at = None
    unverified.source_method = SourceMethod.PUBLIC_SEARCH_DISCOVERY

    fake_sources([[verified, unverified]])
    headers = auth_headers()
    user = await _get_first_user(db)
    await _seed_resume(db, user.id)

    r = client.post("/jobs/search", json={"time_range": "any", "sources": ["fake0"]}, headers=headers)
    search_id = r.json()["search_id"]

    import time

    deadline = time.time() + 15
    while time.time() < deadline:
        status = client.get(f"/jobs/search/{search_id}/status", headers=headers).json()["status"]
        if status in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    r = client.get(f"/jobs/search/{search_id}", headers=headers)
    jobs = {j["title"]: j for j in r.json()["jobs"]}
    assert jobs["Verified Role"]["source_method"] == "AUTHORIZED_FEED"
    assert jobs["Verified Role"]["posted_at_precision"] == "EXACT"
    assert jobs["Verified Role"]["posting_verified"] is True
    assert jobs["Unverified Role"]["source_method"] == "PUBLIC_SEARCH_DISCOVERY"
    assert jobs["Unverified Role"]["posted_at_precision"] == "UNKNOWN"
    assert jobs["Unverified Role"]["posting_verified"] is False


async def _get_first_user(db):
    from sqlalchemy import select

    from app.db.models.user import User

    return (await db.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
