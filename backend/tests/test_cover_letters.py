from tests.helpers import create_cover_letter, seed_job


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def test_generate_without_llm_returns_502(db, client, auth_headers):
    job_id = await seed_job(db)
    r = client.post("/cover-letters", headers=auth_headers(), json={"job_id": job_id})
    assert r.status_code == 502


async def test_cover_letter_crud(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    letter_id = await create_cover_letter(db, user_id, job_id, content="Hello hiring team")

    r = client.get("/cover-letters", headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/cover-letters/{letter_id}", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["content"] == "Hello hiring team"

    r = client.patch(f"/cover-letters/{letter_id}", headers=auth_headers(), json={"content": "Updated letter"})
    assert r.status_code == 200
    assert r.json()["content"] == "Updated letter"

    r = client.patch(f"/cover-letters/{letter_id}", headers=auth_headers(), json={"status": "sent"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent"

    r = client.patch(f"/cover-letters/{letter_id}", headers=auth_headers(), json={"status": "nonsense"})
    assert r.status_code == 422

    assert client.delete(f"/cover-letters/{letter_id}", headers=auth_headers()).status_code == 204
    assert client.get(f"/cover-letters/{letter_id}", headers=auth_headers()).status_code == 404


async def test_cover_letter_isolation(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    letter_id = await create_cover_letter(db, user_id, job_id)

    other = auth_headers("other@example.com")
    assert client.get(f"/cover-letters/{letter_id}", headers=other).status_code == 404
    assert client.patch(f"/cover-letters/{letter_id}", headers=other, json={"content": "hax"}).status_code == 404
    assert client.delete(f"/cover-letters/{letter_id}", headers=other).status_code == 404
