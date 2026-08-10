import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.repositories.job_repo import JobRepository
from app.schemas.job import JobSearch
from app.services.job_enrichment_service import enrich
from app.utils.document_utils import html_to_text

logger = logging.getLogger(__name__)

ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"
JSEARCH_API_URL = "https://jsearch.p.rapidapi.com/search"
GOOGLE_SEARCH_API_URL = "https://www.googleapis.com/customsearch/v1"


def _map_job_type(text: str | None) -> JobType | None:
    if not text:
        return None
    lowered = text.lower()
    if "remote" in lowered:
        return JobType.REMOTE
    if "hybrid" in lowered:
        return JobType.HYBRID
    return JobType.ONSITE


class JobSearchService:
    def __init__(self, db: AsyncSession):
        self.job_repo = JobRepository(db)
        self.db = db

    async def search(self, params: JobSearch) -> list[dict]:
        jobs = await self.job_repo.search(
            query=params.query,
            location=params.location or "",
            country=params.country or "",
            remote_only=bool(params.remote_only),
            salary_min=params.salary_min or 0,
            experience_level=params.experience_level or "",
            skills=params.skills or [],
            page=params.page,
            limit=params.limit,
        )
        return [
            {
                "id": j[0].id,
                "title": j[0].title,
                "company_name": j[1].name if j[1] else None,
                "location": j[0].location,
                "country": j[0].country,
                "job_type": j[0].job_type.value if j[0].job_type else None,
                "salary_min": j[0].salary_min,
                "salary_max": j[0].salary_max,
                "salary_currency": j[0].salary_currency,
                "experience_level": j[0].experience_level,
                "seniority": j[0].seniority,
                "experience_min": j[0].experience_min,
                "experience_max": j[0].experience_max,
                "skills_required": j[0].skills_required,
                "description": j[0].description,
                "source": j[0].source,
                "source_url": j[0].source_url,
                "created_at": j[0].created_at,
            }
            for j in jobs
        ]

    async def fetch_from_adzuna(self, query: str, location: str = "") -> int:
        if not settings.ADZUNA_APP_ID:
            logger.info("Adzuna not configured, skipping fetch")
            return 0
        params: dict[str, str | int] = {
            "app_id": settings.ADZUNA_APP_ID,
            "app_key": settings.ADZUNA_APP_KEY,
            "results_per_page": 20,
            "what": query,
            "where": location,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(ADZUNA_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        created = 0
        for item in data.get("results", []):
            if await self._upsert_job(
                source="adzuna",
                source_url=item.get("redirect_url"),
                title=item.get("title"),
                company_name=(item.get("company") or {}).get("display_name"),
                description=html_to_text(item.get("description")),
                location=(item.get("location") or {}).get("display_name"),
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                posted_at=_parse_datetime(item.get("created")),
                job_type_hint=(item.get("location") or {}).get("area") or "",
            ):
                created += 1
        await self.db.commit()
        logger.info("Adzuna: ingested %d new jobs for query %r", created, query)
        return created

    async def fetch_from_jsearch(self, query: str, location: str = "", country: str | None = None) -> int:
        if not settings.RAPIDAPI_KEY:
            logger.info("jsearch not configured, skipping fetch")
            return 0
        headers = {"X-RapidAPI-Key": settings.RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
        params: dict[str, str] = {
            "query": f"{query} in {location}" if location else query,
            "page": "1",
            "num_pages": "1",
        }
        if country:
            params["country"] = country
        data = await self._get_json(JSEARCH_API_URL, headers=headers, params=params, source="jsearch")
        if not data:
            return 0
        created = 0
        for item in data.get("data", []):
            city = item.get("job_city") or ""
            state = item.get("job_state") or ""
            job_country = item.get("job_country") or ""
            loc = ", ".join(filter(None, [city, state, job_country]))
            if await self._upsert_job(
                source="jsearch",
                source_url=item.get("job_apply_link"),
                title=item.get("job_title"),
                company_name=item.get("employer_name"),
                description=html_to_text(item.get("job_description")),
                location=loc,
                country=job_country,
                salary_min=item.get("job_min_salary"),
                salary_max=item.get("job_max_salary"),
                posted_at=_parse_datetime(item.get("job_posted_at_datetime_utc")),
                job_type_hint=item.get("job_employment_type"),
            ):
                created += 1
        await self.db.commit()
        logger.info("jsearch: ingested %d new jobs for query %r", created, query)
        return created

    async def fetch_from_google_cse(self, query: str) -> int:
        if not settings.GOOGLE_API_KEY or not settings.GOOGLE_CSE_ID:
            logger.info("google cse not configured, skipping fetch")
            return 0
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": settings.GOOGLE_CSE_ID,
            "q": query,
            "num": 10,
            "gl": "in",
        }
        data = await self._get_json(GOOGLE_SEARCH_API_URL, params=params, source="google")
        if not data:
            return 0
        created = 0
        for item in data.get("items", []):
            link = item.get("link")
            title = item.get("title")
            if not title or not link:
                continue
            if await self._upsert_job(
                source="google",
                source_url=link,
                title=title[:255],
                company_name=_domain_name(link),
                description=html_to_text(item.get("snippet")),
                location=None,
                country="India",
                salary_min=None,
                salary_max=None,
                posted_at=None,
                job_type_hint=None,
            ):
                created += 1
        await self.db.commit()
        logger.info("google cse: ingested %d new jobs for query %r", created, query)
        return created

    async def fetch_india(self, queries: list[str]) -> dict:
        """Fetch India-focused jobs from JSearch and Google CSE for the given queries."""
        added = 0
        per_source: dict[str, int] = {}
        for query in queries:
            if settings.RAPIDAPI_KEY:
                created = await self.fetch_from_jsearch(query, country="in")
                added += created
                per_source["jsearch"] = per_source.get("jsearch", 0) + created
            if settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID:
                created = await self.fetch_from_google_cse(query)
                added += created
                per_source["google"] = per_source.get("google", 0) + created
        return {"added": added, "per_source": per_source}

    async def _get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any],
        source: str,
    ) -> dict | None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code in (403, 429):
                logger.warning("%s fetch rejected (%s); skipping", source, resp.status_code)
                return None
            if resp.status_code >= 400:
                resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else None

    async def _upsert_job(
        self,
        *,
        source: str,
        source_url: str | None,
        title: str | None,
        company_name: str | None,
        description: str | None,
        location: str | None,
        country: str | None = None,
        salary_min: int | None,
        salary_max: int | None,
        posted_at: datetime | None,
        job_type_hint: str | None,
    ) -> bool:
        if not title or not source_url:
            return False
        existing = await self.db.execute(select(Job).where(Job.source == source, Job.source_url == source_url))
        if existing.scalar_one_or_none():
            return False

        company = await self._get_or_create_company(company_name or "Unknown")
        enriched = enrich(title, description, None, company_name or "Unknown")
        if enriched["dedupe_key"]:
            dup = await self.db.execute(
                select(Job).where(Job.dedupe_key == enriched["dedupe_key"]).limit(1)
            )
            if dup.scalar_one_or_none():
                return False
        self.db.add(
            Job(
                company_id=company.id,
                title=title,
                description=description,
                requirements=None,
                location=location,
                country=country,
                job_type=_map_job_type(job_type_hint),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="USD",
                experience_level=None,
                seniority=enriched["seniority"],
                experience_min=enriched["experience_min"],
                experience_max=enriched["experience_max"],
                dedupe_key=enriched["dedupe_key"],
                skills_required=enriched["skills_required"],
                source=source,
                source_url=source_url,
                posted_at=posted_at,
            )
        )
        return True

    async def _get_or_create_company(self, name: str) -> Company:
        result = await self.db.execute(select(Company).where(Company.name == name))
        company = result.scalar_one_or_none()
        if company:
            return company
        company = Company(name=name)
        self.db.add(company)
        await self.db.flush()
        return company


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _domain_name(url: str) -> str:
    """Extract a readable domain root from a URL, e.g. https://www.naukri.com/jobs -> naukri.com."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc or ""
    parts = host.lower().split(".")
    if len(parts) > 2 and parts[0] in ("www", "m"):
        parts = parts[1:]
    return ".".join(parts) or "Unknown"
