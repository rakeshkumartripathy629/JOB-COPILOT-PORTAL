from app.services.llm_service import LLMError, LLMService
from tests.helpers import create_resume, seed_job


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def _seed_three_jobs(db):
    ids = []
    for title in ["Python Backend Engineer", "React Frontend Engineer", "Data Scientist"]:
        ids.append(await seed_job(db, title=title, company_name="Acme Corp"))
    return ids


async def test_suggestions_use_llm_scores(db, client, auth_headers, monkeypatch):
    user_id = await _user_id(client, auth_headers())
    await create_resume(db, user_id)
    ids = await _seed_three_jobs(db)
    assert len(ids) == 3

    async def fake_generate_json(self, prompt, *, system=None):
        return {
            "matches": [
                {"id": ids[0], "match_score": 92, "reason": "Strong Python and FastAPI overlap.", "matched_skills": ["Python", "FastAPI"]},
                {"id": ids[1], "match_score": 15, "reason": "No frontend skills in resume.", "matched_skills": []},
                {"id": ids[2], "match_score": 40, "reason": "Some data skills.", "matched_skills": ["SQL"]},
            ]
        }

    monkeypatch.setattr(LLMService, "generate_json", fake_generate_json)
    r = client.get("/jobs/suggestions", headers=auth_headers())
    assert r.status_code == 200, r.text

    by_id = {m["id"]: m for m in r.json()}
    assert len(by_id) == 3
    assert by_id[ids[0]]["match_score"] == 92
    assert by_id[ids[0]]["match_reason"] == "Strong Python and FastAPI overlap."
    assert by_id[ids[0]]["matched_skills"] == ["Python", "FastAPI"]
    assert by_id[ids[1]]["match_score"] == 15
    assert sorted(r.json(), key=lambda m: m["match_score"], reverse=True)[0]["id"] == ids[0]


async def test_suggestions_fallback_matched_skills_heuristic(db, client, auth_headers, monkeypatch):
    user_id = await _user_id(client, auth_headers())
    await create_resume(
        db,
        user_id,
        parsed_data='{"designation": "Backend Developer", "skills": ["Python", "FastAPI", "SQL"]}',
    )
    job_id = await seed_job(db, title="Python Backend Engineer", company_name="Acme Corp")

    async def broken_generate_json(self, prompt, *, system=None):
        raise LLMError("provider down")

    monkeypatch.setattr(LLMService, "generate_json", broken_generate_json)
    r = client.get("/jobs/suggestions", headers=auth_headers())
    assert r.status_code == 200, r.text
    matches = r.json()
    assert len(matches) == 1
    # Job description mentions "Python", so heuristic matched-skills should include it.
    assert matches[0]["id"] == job_id
    assert "Python" in matches[0]["matched_skills"]


async def test_suggestions_fallback_to_heuristic_when_llm_down(db, client, auth_headers, monkeypatch):
    user_id = await _user_id(client, auth_headers())
    await create_resume(db, user_id, parsed_data="Python FastAPI AWS backend engineer.")
    await _seed_three_jobs(db)

    async def broken_generate_json(self, prompt, *, system=None):
        raise LLMError("provider down")

    monkeypatch.setattr(LLMService, "generate_json", broken_generate_json)
    r = client.get("/jobs/suggestions", headers=auth_headers())
    assert r.status_code == 200, r.text
    matches = r.json()
    assert len(matches) == 3
    assert all(m["match_score"] >= 10 for m in matches)
    assert all(m["match_reason"] is None for m in matches)


async def test_suggestions_empty_without_resume(client, auth_headers):
    r = client.get("/jobs/suggestions", headers=auth_headers())
    assert r.status_code == 200
    assert r.json() == []


async def test_suggestions_without_llm_key_falls_back(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    await create_resume(db, user_id)
    await seed_job(db)
    r = client.get("/jobs/suggestions", headers=auth_headers())
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1
    assert r.json()[0]["match_score"] >= 10
