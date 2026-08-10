"""Tests for the advanced resume-job matching + career evidence system."""

import json

import pytest
from sqlalchemy import select

from app.db.models.career import (
    JobMatchEvidence,
    JobRequirementMatch,
)
from app.services.skill_classifier import (
    DIRECT_MATCH,
    NO_EVIDENCE,
    RELATED_MATCH,
    canonicalize_skill,
    classify_requirement,
)
from tests.helpers import create_resume


async def _seed(db, user_id: int, skills, designation="Backend Developer", experience=None):
    await create_resume(
        db,
        user_id,
        parsed_data=json.dumps(
            {
                "designation": designation,
                "skills": skills,
                "experience": experience
                or [
                    "2021 - Present: Backend Developer at Acme",
                    "2020 - 2021: Junior Developer at Beta",
                ],
                "education": ["B.Tech in Computer Science"],
                "summary": "Backend developer.",
            }
        ),
    )


# ------------------------------------------------------------------------------
# Requirement classification (strict direct/related/partial/no-evidence rules)
# ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "req, skills, expected",
    [
        ("MongoDB", ["PostgreSQL"], RELATED_MATCH),
        ("MongoDB", ["MongoDB"], DIRECT_MATCH),
        ("Docker", ["Kubernetes"], RELATED_MATCH),
        ("Kubernetes", ["Kubernetes"], DIRECT_MATCH),
        ("JavaScript", ["Kubernetes"], NO_EVIDENCE),
        ("database", ["PostgreSQL"], NO_EVIDENCE),
        ("k8s", ["Kubernetes"], DIRECT_MATCH),
        ("Python", ["Django"], RELATED_MATCH),
        ("PostgreSQL", ["MySQL"], RELATED_MATCH),
        ("React", ["Angular"], RELATED_MATCH),
    ],
)
def test_requirement_classification(req, skills, expected):
    classification, _matched, _score = classify_requirement(req, skills)
    assert classification == expected, f"{req} vs {skills}: got {classification}, want {expected}"


def test_mongodb_is_never_a_direct_match_for_postgresql():
    classification, matched, _score = classify_requirement("MongoDB", ["PostgreSQL"])
    assert classification != DIRECT_MATCH
    assert classification == RELATED_MATCH
    assert matched == "PostgreSQL"


def test_docker_is_never_a_direct_match_for_kubernetes():
    classification, _m, _s = classify_requirement("Docker", ["Kubernetes"])
    assert classification != DIRECT_MATCH


def test_javascript_is_never_a_match_for_kubernetes():
    classification, _m, _s = classify_requirement("JavaScript", ["Kubernetes"])
    assert classification == NO_EVIDENCE


def test_generic_database_is_never_a_direct_match_for_postgresql():
    classification, _m, _s = classify_requirement("database", ["PostgreSQL"])
    assert classification != DIRECT_MATCH


def test_alias_canonicalization():
    assert canonicalize_skill("k8s") == "kubernetes"
    assert canonicalize_skill("Node.js") == "node.js"
    assert canonicalize_skill("AWS") == "aws"


# ------------------------------------------------------------------------------
# Career Vault
# ------------------------------------------------------------------------------


async def test_rebuild_vault_creates_facts_and_evidence(db, client, auth_headers):
    headers = auth_headers()
    from sqlalchemy import select

    from app.db.models.user import User

    user = (await db.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    await _seed(db, user.id, ["Node.js", "Express", "PostgreSQL", "AWS"])

    r = client.post("/career/index", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["facts_created"] >= 4

    r = client.get("/career/facts", headers=headers)
    assert r.status_code == 200
    facts = r.json()
    names = {f["name"].lower() for f in facts}
    assert "node.js" in names
    assert "postgresql" in names
    types = {f["fact_type"] for f in facts}
    assert "technical_skill" in types
    assert "education" in types
    assert "experience" in types

    r = client.get("/career/evidence", headers=headers)
    assert r.status_code == 200
    evidence = r.json()
    assert len(evidence) >= 4
    assert all(e["career_fact_id"] for e in evidence)

    r = client.get("/career/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["facts_total"] == len(facts)


async def test_vault_is_per_user_isolated(db, client, auth_headers):
    from app.db.models.user import User

    headers = auth_headers()
    user = (await db.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    await _seed(db, user.id, ["Node.js"])
    client.post("/career/index", headers=headers)
    fact_id = client.get("/career/facts", headers=headers).json()[0]["id"]

    other = auth_headers("other@example.com", "Password123!")
    r = client.patch(f"/career/facts/{fact_id}", json={"status": "REJECTED"}, headers=other)
    assert r.status_code == 404

    r = client.get("/career/facts", headers=other)
    assert r.json() == []


async def test_verify_and_reject_facts(db, client, auth_headers):
    from app.db.models.user import User

    headers = auth_headers()
    user = (await db.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    await _seed(db, user.id, ["Node.js"])
    client.post("/career/index", headers=headers)
    fact = client.get("/career/facts", headers=headers).json()[0]

    r = client.patch(f"/career/facts/{fact['id']}", json={"status": "VERIFIED"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["verified_by_user"] is True

    r = client.patch(f"/career/facts/{fact['id']}", json={"status": "BOGUS"}, headers=headers)
    assert r.status_code in (400, 422)

    r = client.patch(f"/career/facts/{fact['id']}", json={"status": "REJECTED"}, headers=headers)
    assert r.status_code == 200
    r = client.get("/career/facts", headers=headers)
    assert r.json()[0]["status"] == "REJECTED"


async def test_rebuild_is_idempotent_and_preserves_user_confirmations(
    db, client, auth_headers
):
    from app.db.models.user import User

    headers = auth_headers()
    user = (await db.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    await _seed(db, user.id, ["Node.js"])
    client.post("/career/index", headers=headers)

    skill_fact = [
        f for f in client.get("/career/facts", headers=headers).json() if f["name"].lower() == "node.js"
    ][0]
    client.patch(f"/career/facts/{skill_fact['id']}", json={"status": "USER_CONFIRMED"}, headers=headers)

    client.post("/career/index", headers=headers)
    facts = client.get("/career/facts", headers=headers).json()
    node = [f for f in facts if f["name"].lower() == "node.js"][0]
    assert node["status"] == "USER_CONFIRMED"
    assert node["verified_by_user"] is True
    assert node["id"] == skill_fact["id"]


# ------------------------------------------------------------------------------
# Advanced match engine
# ------------------------------------------------------------------------------


async def _compute_match(db, client, auth_headers, skills, title="Backend Engineer"):
    from app.db.models.user import User

    headers = auth_headers()
    user = (await db.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    await _seed(db, user.id, skills)
    client.post("/career/index", headers=headers)

    from app.services.job_sources import registry
    from app.services.job_sources.base import JobSource, SourceResult, SourceStatus
    from app.services.live_search_service import run_search_task, start_search
    from tests.test_resume_search import make_job

    class OneSource(JobSource):
        name = "onematch"
        display_name = "One Match"

        def __init__(self, jobs):
            self._jobs = jobs

        async def search(self, query, profile=None):
            return SourceResult(SourceStatus.SUCCESS, jobs=list(self._jobs))

    saved = registry.all()
    registry.clear()
    source = OneSource([make_job(title=title)])
    registry.register(source)
    try:
        search_id = await start_search(
            db, user_id=user.id, time_range="any", remote="any", sources=["onematch"]
        )
        await run_search_task(search_id)
    finally:
        registry.clear()
        for s in saved:
            registry.register(s)
    return headers, user


async def test_advanced_match_scores_are_bounded_and_confidence_reported(
    db, client, auth_headers
):
    headers, _user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"]
    )
    r = client.get("/jobs/1/match", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    for key, value in data.items():
        if key.endswith("_score") or key == "overall_score" or key == "match_confidence":
            assert isinstance(value, int) and 0 <= value <= 100, f"{key}={value}"
    assert data["requirements"], "expected a requirement matrix"
    for req in data["requirements"]:
        assert req["classification"] in {
            "DIRECT_MATCH",
            "RELATED_MATCH",
            "PARTIAL_MATCH",
            "NO_EVIDENCE",
        }
        assert 0 <= req["skill_score"] <= 100


async def test_advanced_match_requirement_matrix_persisted(db, client, auth_headers):
    headers, user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"]
    )
    r = client.get("/jobs/1/requirement-matrix", headers=headers)
    assert r.status_code == 200, r.text
    matrix = r.json()
    assert matrix
    direct = [m for m in matrix if m["classification"] == "DIRECT_MATCH"]
    assert direct, "expected at least one direct skill match for the seeded profile"

    req_ids = {m["requirement_id"] for m in matrix}
    matches = (
        (await db.execute(select(JobRequirementMatch).where(JobRequirementMatch.job_id == 1)))
        .scalars()
        .all()
    )
    assert len(matches) == len(req_ids)

    evidence = (
        (await db.execute(select(JobMatchEvidence).where(JobMatchEvidence.job_id == 1)))
        .scalars()
        .all()
    )
    assert evidence, "expected persisted match evidence"


async def test_critical_missing_never_hidden_by_related_skill(db, client, auth_headers):
    headers, _user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "MySQL"]
    )
    r = client.get("/jobs/1/match", headers=headers)
    assert r.status_code == 200
    data = r.json()
    critical = [m for m in data["requirements"] if m["is_critical"]]
    for req in critical:
        if req["skill"] and req["skill"].lower() in {
            "postgresql", "docker", "kubernetes", "mongodb", "react", "java", "aws", "sql",
        }:
            assert req["classification"] == "NO_EVIDENCE", (
                f"critical requirement {req['requirement']} must stay NO_EVIDENCE (related "
                f"skills must never satisfy a critical requirement)"
            )


async def test_evidence_endpoint_returns_grounded_records(db, client, auth_headers):
    headers, _user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"]
    )
    r = client.get("/jobs/1/evidence", headers=headers)
    assert r.status_code == 200, r.text
    records = r.json()
    assert records
    for rec in records:
        assert rec["evidence_text"]
        assert rec["confidence"] >= 0


# ------------------------------------------------------------------------------
# ShouldApply + ROI
# ------------------------------------------------------------------------------


async def test_should_apply_endpoint(db, client, auth_headers):
    headers, _user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"]
    )
    r = client.get("/jobs/1/should-apply", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["decision"] in {
        "STRONGLY_RECOMMENDED",
        "RECOMMENDED",
        "CONSIDER",
        "LOW_PRIORITY",
        "SKIP",
    }
    assert isinstance(data["confidence"], int) and 0 <= data["confidence"] <= 100
    assert data["reasons"]
    assert isinstance(data["critical_gaps"], list)


async def test_roi_endpoint(db, client, auth_headers):
    headers, _user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"]
    )
    r = client.get("/jobs/1/roi", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 0 <= data["roi_score"] <= 100
    assert data["signals"]
    assert data["notes"]


async def test_match_requires_resume(db, client, auth_headers):
    headers = auth_headers()
    from app.services.job_sources import registry
    from app.services.job_sources.base import JobSource, SourceResult, SourceStatus
    from tests.test_resume_search import make_job

    class OnlySource(JobSource):
        name = "only"
        display_name = "Only"

        async def search(self, query, profile=None):
            return SourceResult(SourceStatus.SUCCESS, jobs=[make_job()])

    saved = registry.all()
    registry.clear()
    registry.register(OnlySource())
    try:
        r = client.post("/jobs/search", json={"time_range": "any", "sources": ["only"]}, headers=headers)
        assert r.status_code == 400  # no resume yet
    finally:
        registry.clear()
        for s in saved:
            registry.register(s)

    r = client.get("/jobs/1/match", headers=headers)
    assert r.status_code in (400, 404)


async def test_other_user_cannot_read_job_match_evidence(db, client, auth_headers):
    headers, _user = await _compute_match(
        db, client, auth_headers, ["Node.js", "Express", "PostgreSQL", "Docker", "AWS"]
    )
    other = auth_headers("other@example.com", "Password123!")
    r = client.get("/jobs/1/evidence", headers=other)
    assert r.status_code in (200, 400)
    rows = (await db.execute(select(JobMatchEvidence).where(JobMatchEvidence.user_id != 1))).scalars().all()
    assert rows == []
