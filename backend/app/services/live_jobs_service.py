"""Fetch real jobs from free public APIs (no keys required) and upsert into the DB."""

import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.repositories.job_repo import JobRepository
from app.services.job_enrichment_service import enrich
from app.utils.document_utils import html_to_text

logger = logging.getLogger(__name__)

SOURCES = [
    ("remotive", "https://remotive.com/api/remote-jobs?limit=100"),
    ("jobicy", "https://jobicy.com/api/v2/remote-jobs?count=100"),
    ("arbeitnow", "https://www.arbeitnow.com/api/job-board-api?limit=50"),
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _map_job_type(text: str) -> JobType:
    lowered = (text or "").lower()
    if "remote" in lowered:
        return JobType.REMOTE
    if "hybrid" in lowered:
        return JobType.HYBRID
    return JobType.ONSITE


def _parse_salary(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    import re

    nums = [int(n) for n in re.findall(r"\d{3,}", text.replace(",", ""))]
    if not nums:
        return None, None
    lo = nums[0]
    hi = nums[1] if len(nums) > 1 else lo
    return lo, hi


def _normalize(source: str, item: dict) -> dict | None:
    if source == "remotive":
        title = item.get("title")
        url = item.get("url")
        if not title or not url:
            return None
        location = item.get("candidate_required_location") or "Remote"
        tags = [str(t).lower() for t in (item.get("tags") or [])]
        job_type = JobType.REMOTE
        category = item.get("category") or ""
        full_text = (item.get("description") or "") + " " + title + " " + " ".join(tags)
        if any(word in full_text.lower() for word in ["finance", "sales", "marketing", "support", "recruit", "customer"]):
            # keep every job; users can filter by search
            pass
        return {
            "title": title,
            "company": item.get("company_name") or "Unknown",
            "description": html_to_text(item.get("description")),
            "location": location,
            "country": None,
            "job_type": job_type,
            "salary_min": None,
            "salary_max": None,
            "source": source,
            "source_url": url,
            "posted_at": _parse_dt(item.get("publication_date")),
            "tags": ",".join(tags),
            "category": category,
        }
    if source == "jobicy":
        title = item.get("jobTitle")
        url = item.get("url")
        if not title or not url:
            return None
        geo = (item.get("jobGeo") or "").lower()
        industry = str(item.get("jobIndustry") or "")
        if "hybrid" in geo:
            job_type = JobType.HYBRID
        elif "remote" in geo or item.get("workFromHome") is True:
            job_type = JobType.REMOTE
        else:
            job_type = JobType.ONSITE
        return {
            "title": title,
            "company": item.get("companyName") or "Unknown",
            "description": html_to_text(item.get("jobDescription")),
            "location": item.get("jobGeo") or "Remote",
            "country": None,
            "job_type": job_type,
            "salary_min": item.get("salaryRangeMin"),
            "salary_max": item.get("salaryRangeMax"),
            "source": source,
            "source_url": url,
            "posted_at": _parse_dt(item.get("datePosted")),
            "tags": industry.lower(),
            "category": industry,
        }
    if source == "arbeitnow":
        title = item.get("title")
        url = item.get("url")
        if not title or not url:
            return None
        remote = bool(item.get("remote"))
        location = item.get("location") or ""
        if remote:
            job_type = JobType.REMOTE
        elif "hybrid" in (item.get("job_types") or []) or "hybrid" in location.lower():
            job_type = JobType.HYBRID
        else:
            job_type = JobType.ONSITE
        salary = item.get("salary") or ""
        salary_min, salary_max = _parse_salary(salary)
        return {
            "title": title,
            "company": item.get("company_name") or "Unknown",
            "description": html_to_text(item.get("description")),
            "location": location or "Remote" if remote else (location or "Germany"),
            "country": None,
            "job_type": job_type,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "source": source,
            "source_url": url,
            "posted_at": _parse_dt(item.get("created_at")),
            "tags": ",".join(str(t).lower() for t in (item.get("tags") or [])),
            "category": ",".join(str(t) for t in (item.get("tags") or [])),
        }
    return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        from dateutil import parser as dt_parser

        parsed = dt_parser.parse(value)
        if isinstance(parsed, datetime):
            return parsed.replace(tzinfo=None)
        return None
    except Exception:
        return None


async def refresh_jobs(db: AsyncSession, limit_per_source: int = 100) -> dict:
    """Fetch jobs from all free sources and upsert them. Returns counts."""
    results: dict[str, int] = {}
    added_total = 0
    skipped_total = 0
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for source, url in SOURCES:
            if source == "arbeitnow":
                url = f"{url}&limit={limit_per_source}"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("jobs", []) if source in ("remotive", "jobicy") else data.get("data", [])
                added, skipped = await _upsert_many(db, source, items)
                results[source] = added
                added_total += added
                skipped_total += skipped
                logger.info("Jobs refresh: %s -> %d added, %d skipped", source, added, skipped)
            except Exception as exc:
                logger.error("Jobs refresh: %s failed: %s", source, exc)
                results[source] = 0
    await db.commit()
    return {
        "added": added_total,
        "skipped": skipped_total,
        "per_source": results,
    }


async def _upsert_many(db: AsyncSession, source: str, items: list[dict]) -> tuple[int, int]:
    repo = JobRepository(db)
    added = 0
    skipped = 0
    for item in items:
        norm = _normalize(source, item)
        if not norm:
            continue
        existing = await repo.get_by_source_url(source, norm["source_url"])
        if existing:
            skipped += 1
            continue
        company = await _get_or_create_company(db, norm["company"])
        enriched = enrich(
            norm["title"],
            norm["description"],
            None,
            norm["company"],
            norm["location"],
        )
        if enriched["dedupe_key"]:
            dup = await repo.get_by_dedupe_key(enriched["dedupe_key"])
            if dup:
                skipped += 1
                continue
        country = norm["country"] or enriched["country"]
        db.add(
            Job(
                company_id=company.id,
                title=norm["title"],
                description=norm["description"],
                requirements=None,
                location=norm["location"],
                country=country,
                job_type=norm["job_type"],
                salary_min=norm["salary_min"],
                salary_max=norm["salary_max"],
                salary_currency="USD",
                experience_level=None,
                seniority=enriched["seniority"],
                experience_min=enriched["experience_min"],
                experience_max=enriched["experience_max"],
                dedupe_key=enriched["dedupe_key"],
                skills_required=enriched["skills_required"],
                source=norm["source"],
                source_url=norm["source_url"],
                posted_at=norm.get("posted_at"),
            )
        )
        added += 1
        if added >= 400:
            break
    return added, skipped


async def _get_or_create_company(db: AsyncSession, name: str) -> Company:
    result = await db.execute(select(Company).where(Company.name == name))
    company = result.scalar_one_or_none()
    if company:
        return company
    company = Company(name=name)
    db.add(company)
    await db.flush()
    return company
