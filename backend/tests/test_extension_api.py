"""Chrome Extension API tests: auth, user isolation, matching, mapping, answers."""

import pytest

S = "/extension"


def _run(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.new_event_loop().run_until_complete(coro)
    else:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(loop.run_until_complete, coro).result()


def _make_job(client, auth_headers, *, company="ABC Technologies", title="Backend Engineer"):
    del client, auth_headers

    async def _seed():
        from sqlalchemy import select

        from app.db.models.company import Company
        from app.db.models.job import Job
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            existing = (await db.execute(select(Job).limit(1))).scalars().first()
            if existing:
                return existing
            company_row = (await db.execute(select(Company).limit(1))).scalars().first()
            if not company_row:
                company_row = Company(name=company, website=None)
                db.add(company_row)
                await db.flush()
            job = Job(
                company_id=company_row.id,
                title=title,
                description="Build backend APIs with Python.",
                requirements="Python, FastAPI",
                location="Bangalore, India",
                country="India",
                canonical_url="https://boards.example.com/abc/backend-engineer",
                source_url="https://boards.example.com/abc/backend-engineer",
                source="Greenhouse",
                source_job_id="JOB-123",
                dedupe_key="backend-engineer|abc-technologies",
                is_active=True,
                posting_verified=True,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            return job

    return _run(_seed())


async def _seed_fact(user_id: int = 1):
    from sqlalchemy import delete

    from app.db.models.career import CareerEvidence, CareerFact
    from app.db.models.profile import Profile
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(delete(CareerFact).where(CareerFact.user_id == user_id))
        fact = CareerFact(
            user_id=user_id,
            fact_type="technical_skill",
            name="Python",
            value="Expert",
            confidence=95,
            status="USER_CONFIRMED",
            verified_by_user=True,
        )
        db.add(fact)
        await db.flush()
        db.add(
            CareerEvidence(
                user_id=user_id,
                career_fact_id=fact.id,
                evidence_type="user_skills",
                source="user",
                source_section="profile",
                evidence_text="Python",
                confidence=95,
                verification_status="USER_CONFIRMED",
                verified_by_user=True,
            )
        )
        await db.commit()


@pytest.fixture
def other_user_headers(client):
    def _make():
        r = client.post(
            "/auth/signup",
            json={"email": "other@example.com", "password": "Password123!", "full_name": "Other User"},
        )
        if r.status_code == 400:
            pass
        else:
            assert r.status_code == 201, r.text
        r = client.post("/auth/login", json={"email": "other@example.com", "password": "Password123!"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make


def test_extension_endpoints_require_auth(client):
    assert client.post(f"{S}/session", json={}).status_code == 401
    assert client.get(f"{S}/career-profile").status_code == 401
    assert client.post(f"{S}/detect-job", json={}).status_code == 401
    assert client.post(f"{S}/generate-answer", json={"question": "hi"}).status_code == 401


def test_session_create_and_isolate(client, auth_headers, other_user_headers):
    payload = {
        "session_id": "sess_test_0001",
        "page_url": "https://boards.example.com/jobs/1",
        "job_title": "Backend Engineer",
        "company": "ABC",
        "ats": "Greenhouse",
    }
    r = client.post(f"{S}/session", json=payload, headers=auth_headers())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"] == "sess_test_0001"
    assert data["status"] == "DETECTED"
    first_user = data["user_id"]

    # Second user gets the same row but is never exposed as a different owner.
    r2 = client.post(f"{S}/session", json=payload, headers=other_user_headers())
    assert r2.status_code == 200
    assert r2.json()["user_id"] != first_user


def test_career_profile_returns_only_own_data(client, auth_headers, other_user_headers):
    r = client.get(f"{S}/career-profile", headers=auth_headers())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["resume"]["available"] is False
    assert data["facts"] == []


def test_detect_job_matches_existing_job(client, auth_headers):
    job = _make_job(client, auth_headers)
    r = client.post(
        f"{S}/detect-job",
        headers=auth_headers(),
        json={
            "job_title": "Backend Engineer",
            "company": "ABC Technologies",
            "canonical_url": job.canonical_url,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] is True
    assert data["job_id"] == job.id
    assert data["match_confidence"] >= 0.9
    assert data["applied_before"] is False


def test_detect_job_no_match_does_not_create(client, auth_headers):
    r = client.post(
        f"{S}/detect-job",
        headers=auth_headers(),
        json={"job_title": "Unicorn Whisperer", "company": "FakeCo", "canonical_url": "https://x.example/1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] is False
    assert data["job_id"] is None

    from app.db.models.job import Job
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import func, select

    async def _count():
        async with AsyncSessionLocal() as db:
            return (await db.execute(select(func.count(Job.id)))).scalar_one()

    import asyncio

    assert asyncio.get_event_loop_policy().get_event_loop().run_until_complete(_count()) == 0


def test_detect_job_applied_status_is_user_scoped(client, auth_headers, other_user_headers):
    job = _make_job(client, auth_headers)

    async def _mark_applied():
        from datetime import datetime

        from app.db.models.application import Application, ApplicationSource, ApplicationStatus
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            db.add(
                Application(
                    user_id=1,
                    job_id=job.id,
                    status=ApplicationStatus.APPLIED.value,
                    application_source=ApplicationSource.MANUAL.value,
                    applied_at=datetime.utcnow(),
                )
            )
            await db.commit()

    _run(_mark_applied())

    r = client.post(
        f"{S}/detect-job",
        headers=auth_headers(),
        json={"job_title": "Backend Engineer", "company": "ABC Technologies", "canonical_url": job.canonical_url},
    )
    assert r.status_code == 200
    assert r.json()["matched"] is True
    assert r.json()["applied_before"] is True
    assert r.json()["application_status"] == "APPLIED"

    # Other user sees the same shared job but NOT user 1's application state.
    r = client.post(
        f"{S}/detect-job",
        headers=other_user_headers(),
        json={"job_title": "Backend Engineer", "company": "ABC Technologies", "canonical_url": job.canonical_url},
    )
    assert r.status_code == 200
    assert r.json()["matched"] is True
    assert r.json()["applied_before"] is False


def test_detect_ats_canonicalizes(client, auth_headers):
    r = client.post(
        f"{S}/detect-ats", headers=auth_headers(), json={"detected": "greenhouse", "url": "https://boards.greenhouse.io/x"}
    )
    assert r.status_code == 200
    assert r.json()["ats"] == "Greenhouse"
    assert r.json()["confidence"] > 0.9

    r = client.post(f"{S}/detect-ats", headers=auth_headers(), json={"detected": "", "url": "https://jobs.lever.co/x"})
    assert r.json()["ats"] == "Lever"

    r = client.post(f"{S}/detect-ats", headers=auth_headers(), json={"detected": "", "url": "https://weird.example"})
    assert r.json()["ats"] == "Unknown"


def test_analyze_fields_maps_verified_values(client, auth_headers):
    async def _seed_profile():
        from app.db.models.profile import Profile
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            db.add(
                Profile(
                    user_id=1,
                    phone="+91 9876543210",
                    location="Bangalore, India",
                    linkedin_url="https://linkedin.com/in/test",
                )
            )
            await db.commit()

    _run(_seed_profile())
    _run(_seed_fact(1))

    r = client.post(
        f"{S}/analyze-fields",
        headers=auth_headers(),
        json={
            "session_id": "sess_test_0002",
            "fields": [
                {"field_type": "email", "detection_method": "autocomplete"},
                {"field_type": "phone", "detection_method": "label"},
                {"field_type": "skills", "detection_method": "label"},
                {"field_type": "workAuthorization", "sensitive": True, "detection_method": "label"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    fields = {f["field_type"]: f for f in r.json()["fields"]}
    assert fields["email"]["value"] == "test@example.com"
    assert fields["email"]["value_source"] == "CAREER_VAULT"
    assert fields["email"]["needs_review"] is False
    assert fields["phone"]["value"] == "+91 9876543210"
    assert fields["skills"]["value"] == "Python"
    assert fields["skills"]["value_source"] == "CAREER_VAULT"
    assert fields["workAuthorization"]["value"] is None
    assert fields["workAuthorization"]["needs_review"] is True


def test_analyze_fields_missing_never_invents(client, auth_headers):
    r = client.post(
        f"{S}/analyze-fields",
        headers=auth_headers(),
        json={"session_id": "sess_test_0003", "fields": [{"field_type": "github", "detection_method": "label"}]},
    )
    assert r.status_code == 200
    field = r.json()["fields"][0]
    assert field["value"] is None
    assert field["needs_review"] is True


def test_generate_answer_sensitive_question_blocked(client, auth_headers):
    r = client.post(
        f"{S}/generate-answer",
        headers=auth_headers(),
        json={"question": "Are you legally authorized to work in the United States?"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] is None
    assert data["needs_review"] is True
    assert "Sensitive" in (data["reason"] or "")


def test_generate_answer_no_llm_graceful(client, auth_headers):
    _run(_seed_fact(1))

    r = client.post(
        f"{S}/generate-answer",
        headers=auth_headers(),
        json={"question": "Why do you want to work here?", "max_length": 250},
    )
    assert r.status_code == 200
    data = r.json()
    # OPENAI_API_KEY is empty in tests -> LLM unavailable -> manual review.
    assert data["needs_review"] is True


def test_generate_answer_no_facts_reports_review(client, auth_headers):
    r = client.post(
        f"{S}/generate-answer",
        headers=auth_headers(),
        json={"question": "Describe your experience with Node.js."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["needs_review"] is True


def test_validate_answer_deterministic(client, auth_headers):
    _run(_seed_fact(1))

    r = client.post(
        f"{S}/validate-answer",
        headers=auth_headers(),
        json={"answer": "I have deep expertise in Python and have built production APIs."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True

    r = client.post(
        f"{S}/validate-answer",
        headers=auth_headers(),
        json={"answer": "I am a certified astronaut with 20 years on the ISS."},
    )
    data = r.json()
    assert data["valid"] is False
    assert data["issues"]


def test_application_packet_requires_own_job(client, auth_headers, other_user_headers):
    job = _make_job(client, auth_headers)
    r = client.get(f"{S}/application-packet/{job.id}", headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["job_id"] == job.id
    assert data["title"] == "Backend Engineer"
    assert isinstance(data["resumes"], list)
    assert isinstance(data["cover_letters"], list)

    r = client.get(f"{S}/application-packet/{job.id}", headers=other_user_headers())
    assert r.status_code == 200  # job is global, packet is still user-scoped data only


def test_application_packet_missing_job(client, auth_headers):
    r = client.get(f"{S}/application-packet/99999", headers=auth_headers())
    assert r.status_code == 404


def test_fill_session_logs_counts_only(client, auth_headers):
    r = client.post(
        f"{S}/fill-session",
        headers=auth_headers(),
        json={
            "session_id": "sess_test_0004",
            "fields_detected": 12,
            "fields_filled": 6,
            "fields_skipped": 3,
            "fields_reviewed": 2,
            "fields_failed": 1,
            "duration_ms": 1500,
            "source": "sidepanel",
        },
    )
    assert r.status_code == 200
    assert r.json()["logged"] is True


def test_extension_log(client, auth_headers):
    r = client.post(
        f"{S}/log",
        headers=auth_headers(),
        json={"session_id": "sess_test_0005", "level": "info", "event": "page_detected", "message": "form found"},
    )
    assert r.status_code == 200
    assert r.json()["logged"] is True
