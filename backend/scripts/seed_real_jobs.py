"""Replace dummy seed jobs with real remote jobs from the Remotive API."""

import asyncio

import httpx
from sqlalchemy import delete, select

from app.db.models.application import Application
from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.db.session import AsyncSessionLocal

DEV_TAGS = {
    "python", "react", "javascript", "typescript", "node", "nodejs", "fullstack",
    "full-stack", "frontend", "backend", "devops", "software", "engineer",
    "developer", "sre", "rust", "go", "java", "sql", "machine learning", "data",
    "ai", "sass", "php", "ruby", "engineering", "cloud", "kubernetes",
}

DEV_CATEGORIES = {"software development", "devops", "data", "engineering"}


def is_dev(item: dict) -> bool:
    category = (item.get("category") or "").lower()
    industry = str(item.get("jobIndustry") or "").lower()
    tags = [t.lower() for t in (item.get("tags") or [])]
    haystack = category + " " + industry + " " + " ".join(tags)
    return category in DEV_CATEGORIES or industry in DEV_CATEGORIES or any(t in haystack for t in DEV_TAGS)


async def main() -> None:
    jobs: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for url in ("https://remotive.com/api/remote-jobs?limit=100", "https://jobicy.com/api/v2/remote-jobs?count=50"):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                jobs.extend(data.get("jobs", []))
            except Exception as exc:
                print(f"fetch {url} failed: {exc}")

    chosen = [item for item in jobs if is_dev(item)][:60]

    async with AsyncSessionLocal() as db:
        seed_jobs = (await db.execute(select(Job.id).where(Job.source == "seed"))).scalars().all()
        if seed_jobs:
            await db.execute(delete(Application).where(Application.job_id.in_(seed_jobs)))
            await db.execute(delete(Job).where(Job.source == "seed"))
            await db.commit()
            print(f"Deleted {len(seed_jobs)} dummy seed jobs.")

        added = 0
        for item in chosen:
            title = item.get("jobTitle") or item.get("title") or ""
            company_name = item.get("companyName") or item.get("company_name") or "Unknown"
            url = item.get("url") or item.get("apply_url") or ""
            desc = item.get("jobDescription") or item.get("description") or ""
            loc = item.get("jobGeo") or item.get("candidate_required_location") or "Remote"
            tags = [t.lower() for t in (item.get("tags") or [])]
            if item.get("jobIndustry"):
                tags.append(str(item["jobIndustry"]).lower())
            if not title or not url:
                continue
            existing = await db.execute(
                select(Job.id).where(Job.source == "remotive", Job.source_url == url)
            )
            if existing.scalar_one_or_none():
                continue
            company = await db.execute(select(Company).where(Company.name == company_name))
            company_row = company.scalar_one_or_none()
            if not company_row:
                company_row = Company(name=company_name)
                db.add(company_row)
                await db.flush()
            db.add(
                Job(
                    company_id=company_row.id,
                    title=title,
                    description=desc,
                    requirements=None,
                    location=loc,
                    job_type=JobType.REMOTE,
                    salary_min=None,
                    salary_max=None,
                    experience_level=None,
                    skills_required=",".join(tags) if tags else None,
                    source="remotive",
                    source_url=url,
                    posted_at=None,
                )
            )
            added += 1
        await db.commit()
        print(f"Added {added} real jobs. Total jobs now:", len((await db.execute(select(Job.id))).scalars().all()))


if __name__ == "__main__":
    asyncio.run(main())
