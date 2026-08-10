from datetime import datetime

from sqlalchemy import select

from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.db.models.user import User
from app.services.job_enrichment_service import (
    classify_seniority,
    enrich,
    experience_range,
    extract_skills,
    make_dedupe_key,
)
from tests.helpers import create_resume, seed_job


async def _seed_enriched_job(
    db,
    title: str,
    company_name: str,
    *,
    country: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    job_type: JobType = JobType.REMOTE,
    description: str = "Build software with Python, React, AWS and Kubernetes.",
) -> int:
    result = await db.execute(select(Company).where(Company.name == company_name))
    company = result.scalar_one_or_none()
    if not company:
        company = Company(name=company_name)
        db.add(company)
        await db.flush()
    fields = enrich(title, description, None, company_name)
    job = Job(
        company_id=company.id,
        title=title,
        description=description,
        location="Remote",
        country=country,
        job_type=job_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="USD",
        seniority=fields["seniority"],
        experience_min=fields["experience_min"],
        experience_max=fields["experience_max"],
        dedupe_key=fields["dedupe_key"],
        skills_required=fields["skills_required"],
        source="test",
        source_url=f"https://test.example/{company_name}-{title}",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job.id


# ---- Enrichment units ----


def test_extract_skills_detects_keywords():
    skills = extract_skills("Senior Python developer building FastAPI services with PostgreSQL and Docker")
    assert "python" in skills
    assert "fastapi" in skills
    assert "postgresql" in skills
    assert "docker" in skills


def test_extract_skills_empty_text():
    assert extract_skills(None) == []
    assert extract_skills("") == []


def test_extract_skills_word_boundaries():
    # "go" should not match inside "google" or "good"
    assert "go" not in extract_skills("google cloud engineer with good communication")
    assert "c" not in extract_skills("c programming" and "machine learning")
    assert "r" not in extract_skills("architect role" and "software")


def test_classify_seniority_and_experience():
    assert classify_seniority("Senior Software Engineer") == "Senior"
    assert classify_seniority("Junior Data Analyst") == "Junior"
    assert classify_seniority("Staff ML Engineer") == "Staff"
    assert classify_seniority("Head of Marketing") == "Head"
    assert classify_seniority("Software Engineer") is None
    assert experience_range("Senior") == (5, 8)
    assert experience_range("Intern") == (0, 0)
    assert experience_range(None) == (None, None)


def test_make_dedupe_key_normalizes():
    assert make_dedupe_key("Senior Backend Engineer (Remote)", "Acme Corp") == (
        make_dedupe_key("Senior Backend Engineer", "Acme Corp")
    )
    assert make_dedupe_key(" Backend  Engineer! ", "Acme") == "backend engineer|acme"


def test_enrich_returns_all_fields():
    fields = enrich("Lead Data Scientist", "Machine learning with Python, PyTorch and SQL.", None, "BigCo")
    assert fields["seniority"] == "Lead"
    assert fields["experience_min"] == 5
    assert "machine learning" in (fields["skills_required"] or "")
    assert fields["dedupe_key"] == "lead data scientist|bigco"


# ---- Intel API ----


async def test_intel_summary(db, client, auth_headers):
    await _seed_enriched_job(db, "Senior Python Developer", "Acme", country="India", salary_min=60000, salary_max=90000)
    await _seed_enriched_job(db, "Backend Engineer", "Acme", country="India", salary_min=50000, salary_max=80000)
    await _seed_enriched_job(db, "Frontend Engineer", "Beta", country="United States", job_type=JobType.ONSITE)

    r = client.get("/jobs/intel/summary", headers=auth_headers())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_jobs"] == 3
    assert data["distinct_companies"] == 2
    assert data["median_salary"] is not None
    assert data["top_skills"]

    r_india = client.get("/jobs/intel/summary?country=India", headers=auth_headers())
    assert r_india.status_code == 200
    assert r_india.json()["total_jobs"] == 2


async def test_intel_skills_and_companies(db, client, auth_headers):
    await _seed_enriched_job(db, "Senior Python Developer", "Acme", country="India")
    await _seed_enriched_job(db, "Backend Engineer", "Acme", country="India")

    r = client.get("/jobs/intel/skills?limit=5", headers=auth_headers())
    assert r.status_code == 200, r.text
    skills = r.json()
    assert skills
    top = skills[0]
    assert top["count"] >= 2
    assert any(s["skill"] == "python" for s in skills)

    r = client.get("/jobs/intel/skills?query=pyt", headers=auth_headers())
    assert r.status_code == 200
    assert all("pyt" in s["skill"] for s in r.json())

    r = client.get("/jobs/intel/companies?limit=5", headers=auth_headers())
    assert r.status_code == 200, r.text
    assert r.json()[0]["company"] == "Acme"
    assert r.json()[0]["job_count"] == 2


async def test_intel_salary_benchmarks(db, client, auth_headers):
    await _seed_enriched_job(db, "Senior Python Developer", "Acme", salary_min=70000, salary_max=90000)
    await _seed_enriched_job(db, "Senior Backend Engineer", "Beta", salary_min=80000, salary_max=100000)
    await _seed_enriched_job(db, "Junior Developer", "Gamma", salary_min=40000, salary_max=50000)

    r = client.get("/jobs/intel/salary", headers=auth_headers())
    assert r.status_code == 200, r.text
    rows = r.json()
    by_band = {row["seniority"]: row for row in rows}
    assert by_band["Senior"]["count"] == 2
    assert by_band["Senior"]["median_salary"] == 85000


async def test_intel_trends(db, client, auth_headers):
    job_id = await seed_job(db, title="Software Engineer")
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one()
    job.posted_at = datetime.utcnow()
    await db.commit()

    r = client.get("/jobs/intel/trends?days=7", headers=auth_headers())
    assert r.status_code == 200, r.text
    points = r.json()
    assert len(points) == 7
    assert sum(p["count"] for p in points) == 1


async def test_intel_profile_uses_resume_skills(db, client, auth_headers):
    headers = auth_headers(email="intel@example.com")
    result = await db.execute(select(User).where(User.email == "intel@example.com"))
    user = result.scalar_one()
    await create_resume(
        db,
        user.id,
        parsed_data='{"designation": "Python Developer", "skills": ["Python", "FastAPI", "React"]}',
    )
    await _seed_enriched_job(db, "Senior Python Developer", "Acme", description="Python and FastAPI")
    await _seed_enriched_job(db, "React Frontend Engineer", "Beta", description="React and TypeScript")

    r = client.get("/jobs/intel/profile", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["has_resume"] is True
    assert data["coverage_score"] > 0
    assert data["total_jobs"] == 2
    assert data["target_jobs_count"] >= 1


async def test_enrich_endpoint_is_idempotent(db, client, auth_headers):
    job_id = await seed_job(db, title="Senior Python Developer", company_name="Acme")
    r = client.post("/jobs/enrich", headers=auth_headers())
    assert r.status_code == 200, r.text
    first = r.json()
    assert first["updated"] >= 1

    r2 = client.post("/jobs/enrich", headers=auth_headers())
    assert r2.status_code == 200
    assert r2.json()["updated"] == 0

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one()
    assert job.seniority == "Senior"
    assert "python" in (job.skills_required or "")
    assert job.salary_currency == "USD"
