from app.db.models.application import ApplicationStatus
from tests.helpers import create_application, seed_job


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def test_analytics_empty(db, client, auth_headers):
    r = client.get("/analytics/me", headers=auth_headers())
    assert r.status_code == 200, r.text
    metrics = r.json()["metrics"]
    assert metrics["total_applications"] == 0
    assert metrics["response_rate_percent"] == 0
    assert r.json()["insights"]


async def test_analytics_counts(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    j1 = await seed_job(db, title="Backend Engineer")
    j2 = await seed_job(db, title="Frontend Engineer")
    await create_application(db, user_id, j1, ApplicationStatus.DRAFT)
    await create_application(db, user_id, j2, ApplicationStatus.INTERVIEW)

    r = client.get("/analytics/me", headers=auth_headers())
    assert r.status_code == 200, r.text
    metrics = r.json()["metrics"]
    assert metrics["total_applications"] == 2
    assert metrics["interviews"] == 1
    assert metrics["applications_by_status"]["DRAFT"] == 1
    assert metrics["applications_by_status"]["INTERVIEW"] == 1
    assert metrics["response_rate_percent"] == 100
