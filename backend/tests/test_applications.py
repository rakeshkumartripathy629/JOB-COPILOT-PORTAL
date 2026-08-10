from tests.helpers import create_application, seed_job


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def test_application_flow(db, client, auth_headers):
    job_id = await seed_job(db)
    r = client.post("/applications", headers=auth_headers(), json={"job_id": job_id})
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    assert r.json()["status"] == "READY"
    assert r.json()["job_title"] == "Software Engineer"

    r = client.post("/applications", headers=auth_headers(), json={"job_id": job_id})
    assert r.status_code == 409

    r = client.get("/applications", headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.post(f"/applications/{app_id}/status", headers=auth_headers(), json={"status": "APPLIED"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPLIED"
    assert r.json()["applied_at"] is not None

    r = client.post(f"/applications/{app_id}/status", headers=auth_headers(), json={"status": "INTERVIEW"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "INTERVIEW"
    assert r.json()["responded_at"] is not None

    r = client.patch(f"/applications/{app_id}", headers=auth_headers(), json={"notes": "Follow up next week"})
    assert r.status_code == 200
    assert r.json()["notes"] == "Follow up next week"

    assert client.delete(f"/applications/{app_id}", headers=auth_headers()).status_code == 204


async def test_invalid_status_rejected(db, client, auth_headers):
    job_id = await seed_job(db)
    r = client.post("/applications", headers=auth_headers(), json={"job_id": job_id})
    app_id = r.json()["id"]
    r = client.post(f"/applications/{app_id}/status", headers=auth_headers(), json={"status": "nonsense"})
    assert r.status_code == 422

    r = client.post(f"/applications/{app_id}/status", headers=auth_headers(), json={"status": "APPLIED"})
    assert r.status_code == 200
    r = client.post(f"/applications/{app_id}/status", headers=auth_headers(), json={"status": "REJECTED"})
    assert r.status_code == 200
    r = client.post(f"/applications/{app_id}/status", headers=auth_headers(), json={"status": "APPLIED"})
    assert r.status_code == 422


async def test_user_cannot_touch_others_application(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    app_id = await create_application(db, user_id, job_id)

    other = auth_headers("other@example.com")
    assert client.post(f"/applications/{app_id}/status", headers=other, json={"status": "OFFER"}).status_code == 404
    assert client.delete(f"/applications/{app_id}", headers=other).status_code == 404
