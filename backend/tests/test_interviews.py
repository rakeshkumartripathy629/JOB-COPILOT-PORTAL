from app.services.llm_service import LLMService
from tests.helpers import create_interview_question, seed_job


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def test_generate_without_llm_returns_502(db, client, auth_headers):
    job_id = await seed_job(db)
    r = client.post(
        "/interviews/questions",
        headers=auth_headers(),
        json={"job_id": job_id, "categories": ["behavioral"]},
    )
    assert r.status_code == 502


async def test_evaluate_answer_uses_llm(db, client, auth_headers, monkeypatch):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    q_id = await create_interview_question(db, user_id, job_id)

    async def fake_generate_json(self, prompt, *, system=None):
        return {
            "score": 78,
            "strengths": "Good structure and STAR method.",
            "improvements": "Add a concrete metric.",
            "model_answer": "A strong sample answer.",
        }

    monkeypatch.setattr(LLMService, "generate_json", fake_generate_json)
    r = client.post(
        f"/interviews/questions/{q_id}/evaluate",
        headers=auth_headers(),
        json={"answer": "I led a project that improved load times."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["question_id"] == q_id
    assert body["score"] == 78
    assert body["strengths"] == "Good structure and STAR method."
    assert body["improvements"].startswith("Add")
    assert body["model_answer"] == "A strong sample answer."


async def test_evaluate_answer_ownership(db, client, auth_headers, monkeypatch):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    q_id = await create_interview_question(db, user_id, job_id)

    async def fake_generate_json(self, prompt, *, system=None):
        return {"score": 50, "strengths": "s", "improvements": "i", "model_answer": "m"}

    monkeypatch.setattr(LLMService, "generate_json", fake_generate_json)
    other = auth_headers("other@example.com")
    assert (
        client.post(
            f"/interviews/questions/{q_id}/evaluate",
            headers=other,
            json={"answer": "Some answer that is long enough."},
        ).status_code
        == 404
    )


async def test_evaluate_answer_unknown_question(client, auth_headers):
    r = client.post(
        "/interviews/questions/9999/evaluate",
        headers=auth_headers(),
        json={"answer": "Some answer that is long enough."},
    )
    assert r.status_code == 404


async def test_evaluate_answer_without_llm_returns_502(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    q_id = await create_interview_question(db, user_id, job_id)
    r = client.post(
        f"/interviews/questions/{q_id}/evaluate",
        headers=auth_headers(),
        json={"answer": "Some answer that is long enough."},
    )
    assert r.status_code == 502


async def test_question_list_and_delete(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    q_id = await create_interview_question(db, user_id, job_id)

    r = client.get("/interviews/questions", headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["question"] == "Tell me about yourself?"

    r = client.get(f"/interviews/questions?job_id={job_id}", headers=auth_headers())
    assert len(r.json()) == 1

    assert client.delete(f"/interviews/questions/{q_id}", headers=auth_headers()).status_code == 204
    assert client.get("/interviews/questions", headers=auth_headers()).json() == []


async def test_question_isolation(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    q_id = await create_interview_question(db, user_id, job_id)

    other = auth_headers("other@example.com")
    r = client.get("/interviews/questions", headers=other)
    assert r.status_code == 200
    assert r.json() == []
    assert client.delete(f"/interviews/questions/{q_id}", headers=other).status_code == 404
