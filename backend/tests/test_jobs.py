from tests.helpers import seed_job


async def test_search(db, client, auth_headers):
    job_id = await seed_job(db)
    r = client.get("/jobs/search?query=engineer", headers=auth_headers())
    assert r.status_code == 200, r.text
    assert any(j["id"] == job_id for j in r.json())

    r = client.get("/jobs/search?query=doesnotexist", headers=auth_headers())
    assert r.status_code == 200
    assert r.json() == []


async def test_get_job_detail(db, client, auth_headers):
    job_id = await seed_job(db)
    r = client.get(f"/jobs/{job_id}", headers=auth_headers())
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Software Engineer"
    assert r.json()["company_name"] == "Acme Corp"


async def test_get_job_not_found(db, client, auth_headers):
    assert client.get("/jobs/999", headers=auth_headers()).status_code == 404


async def test_save_unsave(db, client, auth_headers):
    job_id = await seed_job(db)
    assert client.post(f"/jobs/{job_id}/save", headers=auth_headers()).status_code == 200
    assert client.post(f"/jobs/{job_id}/save", headers=auth_headers()).status_code == 200
    r = client.get("/applications", headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert client.delete(f"/jobs/{job_id}/save", headers=auth_headers()).status_code == 200
    r = client.get("/applications", headers=auth_headers())
    assert len(r.json()) == 0


async def test_suggestions(db, client, auth_headers):
    await seed_job(db)
    r = client.get("/jobs/suggestions", headers=auth_headers())
    assert r.status_code == 200
