"""Application Management + Tracking + CRM - mandatory acceptance tests."""

from datetime import datetime, timedelta

from app.db.models.application import (
    Application,
    ApplicationSnapshot,
    ApplicationStatus,
)
from app.db.models.job import JobType
from app.repositories.resume_repo import ResumeRepository
from tests.helpers import create_application, seed_job


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def test_create_application_from_real_job_creates_snapshot(db, client, auth_headers):
    job_id = await seed_job(db, title="Backend Engineer", company_name="Globex", location="Berlin")
    headers = auth_headers()
    r = client.post("/applications", headers=headers, json={"job_id": job_id, "priority": "HIGH", "tags": ["hot"]})
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    assert r.json()["status"] == "READY"
    assert r.json()["priority"] == "HIGH"
    assert r.json()["job_title"] == "Backend Engineer"

    detail = client.get(f"/applications/{app_id}", headers=headers).json()
    assert detail["snapshot"] is not None
    assert detail["snapshot"]["job_title"] == "Backend Engineer"
    assert detail["snapshot"]["company_name"] == "Globex"
    assert detail["snapshot"]["location"] == "Berlin"
    assert detail["tags"] == ["hot"]
    assert len(detail["timeline"]) >= 1


async def test_cannot_create_application_for_missing_job(db, client, auth_headers):
    r = client.post("/applications", headers=auth_headers(), json={"job_id": 999999})
    assert r.status_code == 404, r.text


async def test_duplicate_protection_same_job(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    assert client.post("/applications", headers=headers, json={"job_id": job_id}).status_code == 201
    r = client.post("/applications", headers=headers, json={"job_id": job_id})
    assert r.status_code == 409, r.text


async def test_duplicate_protection_same_canonical_job_from_other_source(db, client, auth_headers):
    job1 = await seed_job(db, source="linkedin", source_url="https://linkedin.com/jobs/1", canonical_url="https://company.com/careers/engineer", source_job_id="LI-1")
    job2 = await seed_job(db, source="indeed", source_url="https://indeed.com/viewjob/1", canonical_url="https://company.com/careers/engineer", source_job_id="IN-1")
    headers = auth_headers()
    assert client.post("/applications", headers=headers, json={"job_id": job1}).status_code == 201
    r = client.post("/applications", headers=headers, json={"job_id": job2})
    assert r.status_code == 409, r.text


async def test_different_jobs_can_be_applied(db, client, auth_headers):
    j1 = await seed_job(db, title="Engineer A", company_name="Acme")
    j2 = await seed_job(db, title="Engineer B", company_name="Globex")
    headers = auth_headers()
    assert client.post("/applications", headers=headers, json={"job_id": j1}).status_code == 201
    assert client.post("/applications", headers=headers, json={"job_id": j2}).status_code == 201
    assert len(client.get("/applications", headers=headers).json()) == 2


async def test_document_versions_frozen_at_creation(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    resume = await ResumeRepository(db).create(
        {"user_id": user_id, "title": "Main", "file_path": "/tmp/r.pdf", "file_type": "pdf"}
    )
    version = await ResumeRepository(db).create_version(
        {"resume_id": resume.id, "user_id": user_id, "content": "ORIGINAL VERSION CONTENT", "version_label": "v1"}
    )
    job_id = await seed_job(db)
    headers = auth_headers()
    r = client.post(
        "/applications",
        headers=headers,
        json={"job_id": job_id, "resume_version_id": version.id},
    )
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]

    docs = client.get(f"/applications/{app_id}/documents", headers=headers).json()
    assert len(docs) == 1
    assert docs[0]["doc_type"] == "RESUME"

    # Alter the version afterwards; the frozen copy must not change.
    version.content = "CHANGED LATER"
    db.add(version)
    await db.commit()

    url = docs[0]["download_url"]
    download = client.get(url, headers=headers)
    assert download.status_code == 200
    assert "ORIGINAL VERSION CONTENT" in download.text


async def test_document_download_requires_valid_signature(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]
    # No documents were linked -> list is empty, nothing to download.
    docs = client.get(f"/applications/{app_id}/documents", headers=headers).json()
    assert docs == []

    # A forged token must be rejected.
    r = client.get(f"/applications/{app_id}/documents/1/download?token=forged", headers=headers)
    assert r.status_code == 403


async def test_status_transitions_recorded_and_validated(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]

    flow = ["DRAFT", "READY", "APPLIED", "VIEWED", "RECRUITER_CONTACT", "ASSESSMENT", "INTERVIEW", "TECHNICAL_ROUND", "FINAL_ROUND", "OFFER"]
    for s in flow:
        r = client.post(f"/applications/{app_id}/status", headers=headers, json={"status": s, "reason": "moving on"})
        assert r.status_code == 200, (s, r.text)

    timeline = client.get(f"/applications/{app_id}/timeline", headers=headers).json()
    # creation entry + every transition
    assert len(timeline) == len(flow) + 1
    assert timeline[0]["new_status"] == "OFFER"


async def test_rejected_requires_explicit_reopen(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "APPLIED"}).status_code == 200
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "REJECTED"}).status_code == 200

    # Direct Rejected -> Applied is invalid.
    r = client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "APPLIED"})
    assert r.status_code == 422, r.text

    # Reopen via DRAFT, then move forward again.
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "DRAFT", "reason": "reopening"}).status_code == 200
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "READY"}).status_code == 200
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "APPLIED"}).status_code == 200

    audit = client.get(f"/applications/{app_id}/audit", headers=headers).json()
    assert any("reopened" in (a.get("metadata") or "") for a in audit)


async def test_notes_and_tags(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]

    r = client.post(f"/applications/{app_id}/notes", headers=headers, json={"note": "Called recruiter"})
    assert r.status_code == 201
    r = client.post(f"/applications/{app_id}/notes", headers=headers, json={"note": "Sent portfolio"})
    assert r.status_code == 201
    notes = client.get(f"/applications/{app_id}/notes", headers=headers).json()
    assert len(notes) == 2

    assert client.post(f"/applications/{app_id}/tags", headers=headers, json={"tag": "priority"}).status_code == 201
    assert client.post(f"/applications/{app_id}/tags", headers=headers, json={"tag": "remote"}).status_code == 201
    tags = client.get(f"/applications/{app_id}/tags", headers=headers).json()
    assert tags == ["priority", "remote"]
    assert client.delete(f"/applications/{app_id}/tags/remote", headers=headers).status_code == 200
    assert client.get(f"/applications/{app_id}/tags", headers=headers).json() == ["priority"]


async def test_reminder_creates_notification(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]
    due = (datetime.utcnow() + timedelta(days=2)).isoformat()
    r = client.post(f"/applications/{app_id}/reminders", headers=headers, json={"reminder_type": "INTERVIEW", "due_at": due})
    assert r.status_code == 201, r.text
    reminder_id = r.json()["id"]

    reminders = client.get("/applications/reminders", headers=headers).json()
    assert any(x["id"] == reminder_id for x in reminders)

    notifications = client.get("/notifications", headers=headers).json()
    assert any("Reminder set" in n["title"] for n in notifications)

    r = client.post(f"/applications/reminders/{reminder_id}/complete", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "DONE"


async def test_followup_recommendation_logic(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "APPLIED"}).status_code == 200

    # Back-date the application to 8 days ago with no response.
    app = await db.get(Application, app_id)
    app.applied_at = datetime.utcnow() - timedelta(days=8)
    await db.commit()

    r = client.post(f"/applications/{app_id}/follow-up", headers=headers, json={"mode": "professional"})
    assert r.status_code == 200, r.text
    assert r.json()["recommended"] is True
    assert "follow up" in r.json()["message"].lower()

    # A fresh application should not recommend a follow-up yet.
    job2 = await seed_job(db, title="Fresh Role", company_name="Startup")
    app2_id = client.post("/applications", headers=headers, json={"job_id": job2}).json()["id"]
    assert client.post(f"/applications/{app2_id}/status", headers=headers, json={"status": "APPLIED"}).status_code == 200
    r = client.post(f"/applications/{app2_id}/follow-up", headers=headers, json={"mode": "short"})
    assert r.json()["recommended"] is False


async def test_needs_attention_lists_due_followups(db, client, auth_headers):
    job_id = await seed_job(db)
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]
    assert client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "APPLIED"}).status_code == 200

    app = await db.get(Application, app_id)
    app.applied_at = datetime.utcnow() - timedelta(days=12)
    await db.commit()

    items = client.get("/applications/needs-attention", headers=headers).json()
    assert any(i["kind"] == "FOLLOW_UP" and i["application_id"] == app_id for i in items)


async def test_analytics_does_not_count_drafts(db, client, auth_headers):
    headers = auth_headers()
    user_id = await _user_id(client, headers)
    j1 = await seed_job(db, title="A", company_name="C1")
    j2 = await seed_job(db, title="B", company_name="C2")
    j3 = await seed_job(db, title="C", company_name="C3")
    j4 = await seed_job(db, title="D", company_name="C4")

    # 3 submitted + 1 offer + 2 responses, plus 1 draft (must be excluded).
    app1 = await create_application(db, user_id, j1, ApplicationStatus.APPLIED)
    app2 = await create_application(db, user_id, j2, ApplicationStatus.OFFER)
    app3 = await create_application(db, user_id, j3, ApplicationStatus.INTERVIEW)
    await create_application(db, user_id, j4, ApplicationStatus.DRAFT)


    for a in (app1, app2, app3):
        db.add(ApplicationSnapshot(application_id=a, user_id=user_id, job_title="x"))
    await db.commit()

    analytics = client.get("/applications/analytics", headers=headers).json()
    assert analytics["total_applications"] == 4
    assert analytics["drafts"] == 1
    assert analytics["applied"] == 3
    assert analytics["offers"] == 1
    assert analytics["interviews"] == 2
    assert analytics["offer_rate"] == round(100 / 3)
    assert analytics["funnel"]["applied"] == 3


async def test_performance_not_enough_data_notice(db, client, auth_headers):
    job_id = await seed_job(db, title="Lonely Role", company_name="Solo Corp")
    headers = auth_headers()
    app_id = client.post("/applications", headers=headers, json={"job_id": job_id}).json()["id"]
    client.post(f"/applications/{app_id}/status", headers=headers, json={"status": "APPLIED"})
    performance = client.get("/applications/performance", headers=headers).json()
    by_role = performance["by_role"]
    assert len(by_role) == 1
    assert by_role[0]["notice"] == "Not enough data (fewer than 3 applications)."


async def test_csv_export(db, client, auth_headers):
    job_id = await seed_job(db, title="CSV Role", company_name="Data Co")
    headers = auth_headers()
    client.post("/applications", headers=headers, json={"job_id": job_id, "tags": ["export"]})
    r = client.get("/applications/export.csv", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "id,job_id,job_title" in r.text
    assert "CSV Role" in r.text
    assert "Data Co" in r.text


async def test_analytics_include_missing_data_for_invalid_db(db, client, auth_headers):
    # Empty analytics for a fresh user must be zeroed, not an error.
    headers = auth_headers("fresh@example.com")
    analytics = client.get("/applications/analytics", headers=headers).json()
    assert analytics["total_applications"] == 0
    assert analytics["applied"] == 0
    assert analytics["response_rate"] == 0


async def test_user_isolation(db, client, auth_headers):
    user_a = await _user_id(client, auth_headers())
    job_id = await seed_job(db)
    app_id = await create_application(db, user_a, job_id, ApplicationStatus.APPLIED)

    other = auth_headers("other@example.com")
    assert client.get(f"/applications/{app_id}", headers=other).status_code == 404
    assert client.get(f"/applications/{app_id}/notes", headers=other).status_code == 404
    assert client.get(f"/applications/{app_id}/timeline", headers=other).status_code == 404
    assert client.get(f"/applications/{app_id}/documents", headers=other).status_code == 404
    assert client.post(f"/applications/{app_id}/status", headers=other, json={"status": "OFFER"}).status_code == 404


async def test_list_filters_and_sort(db, client, auth_headers):
    j1 = await seed_job(db, title="Remote Python Dev", company_name="Acme", location="Remote", job_type=JobType.REMOTE)
    j2 = await seed_job(db, title="Office Java Dev", company_name="Globex", location="Berlin", job_type=JobType.HYBRID)
    headers = auth_headers()
    client.post("/applications", headers=headers, json={"job_id": j1})
    client.post("/applications", headers=headers, json={"job_id": j2})

    r = client.get("/applications", headers=headers, params={"search": "python"})
    assert len(r.json()) == 1
    assert r.json()[0]["job_title"] == "Remote Python Dev"

    r = client.get("/applications", headers=headers, params={"company": "Globex"})
    assert len(r.json()) == 1
    assert r.json()[0]["company_name"] == "Globex"

    r = client.get("/applications", headers=headers, params={"location": "Berlin"})
    assert len(r.json()) == 1

    r = client.get("/applications", headers=headers, params={"remote": "REMOTE"})
    assert len(r.json()) == 1

    r = client.get("/applications", headers=headers, params={"status": "READY"})
    assert len(r.json()) == 2

    r = client.get("/applications", headers=headers, params={"sort": "oldest"})
    assert len(r.json()) == 2
