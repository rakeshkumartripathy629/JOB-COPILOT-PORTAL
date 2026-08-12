"""JSearch (RapidAPI) source.

Requires a RapidAPI key subscribed to the JSearch API. Reports UNAVAILABLE when the key
is missing or not subscribed.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.config import settings
from app.services.job_sources.base import (
    JobSource,
    NormalizedJob,
    SourceError,
    SourceMethod,
    SourceResult,
    SourceStatus,
)
from app.services.job_sources.http import SourceHTTPClient
from app.services.job_sources.portal import identify_portal
from app.utils.document_utils import html_to_text

logger = logging.getLogger(__name__)

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"

COUNTRY_CODE = {
    "india": "in",
    "united states": "us",
    "usa": "us",
    "united kingdom": "gb",
    "germany": "de",
    "canada": "ca",
    "australia": "au",
    "netherlands": "nl",
    "france": "fr",
    "spain": "es",
    "portugal": "pt",
    "switzerland": "ch",
    "poland": "pl",
    "ireland": "ie",
    "sweden": "se",
}


class JSearchSource(JobSource):
    name = "jsearch"
    display_name = "JSearch"
    portal = "JSearch"
    source_method = SourceMethod.OFFICIAL_API

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=25, min_interval=1.5, retries=2)

    def is_available(self) -> bool:
        return bool(settings.RAPIDAPI_KEY)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        if not self.is_available():
            return SourceResult(
                SourceStatus.UNAVAILABLE,
                error="JSearch unavailable: RAPIDAPI_KEY not configured.",
            )
        country = _pick_country(profile)
        try:
            resp = await self._client.get(
                JSEARCH_URL,
                params={"query": query, "page": "1", "num_pages": "1", "country": country or "us"},
                headers={
                    "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                },
            )
        except SourceError as exc:
            return SourceResult(SourceStatus.ERROR, error=exc.message)
        if resp.status_code in (401, 403):
            return SourceResult(
                SourceStatus.UNAVAILABLE,
                error="JSearch unavailable: the RapidAPI key is not subscribed to this API.",
            )
        if resp.status_code == 429:
            return SourceResult(SourceStatus.RATE_LIMITED, error="JSearch rate limited (HTTP 429).")
        if resp.status_code >= 400:
            return SourceResult(SourceStatus.ERROR, error=f"JSearch returned HTTP {resp.status_code}.")
        data = resp.json()
        jobs = [n for item in data.get("data", []) if (n := self.normalize_job(item)) and self.validate_job(n)]
        if not jobs:
            return SourceResult(SourceStatus.EMPTY, jobs=jobs)
        return SourceResult(SourceStatus.SUCCESS, jobs=jobs)

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        title = raw.get("job_title")
        url = raw.get("job_apply_link")
        if not title or not url:
            return None
        city = raw.get("job_city") or ""
        state = raw.get("job_state") or ""
        country = raw.get("job_country") or ""
        loc = ", ".join(filter(None, [city, state, country])) or None
        portal = identify_portal(url)
        now = datetime.utcnow()
        return NormalizedJob(
            title=str(title),
            company=(raw.get("employer_name") or "Unknown"),
            company_website=raw.get("employer_website"),
            description=html_to_text(raw.get("job_description")),
            location=loc,
            country=country or None,
            city=city or None,
            remote_type=_remote_type(raw),
            employment_type=(raw.get("job_employment_type") or "").lower() or None,
            salary_min=_to_int(raw.get("job_min_salary")),
            salary_max=_to_int(raw.get("job_max_salary")),
            salary_currency=raw.get("job_salary_currency") or "USD",
            skills=[str(s) for s in (raw.get("job_required_skills") or []) if str(s).strip()][:20],
            posted_at=_parse_dt(raw.get("job_posted_at_datetime_utc")),
            discovered_at=now,
            last_verified_at=now,
            source=portal if portal != "Unknown" else "JSearch",
            search_source="jsearch",
            source_job_id=str(raw.get("job_id")) if raw.get("job_id") else None,
            source_url=str(url),
            canonical_url=str(url),
            application_url=str(url),
            source_metadata={"publisher": raw.get("job_publisher"), "google_link": raw.get("job_google_link")},
        )


def _pick_country(profile: object | None) -> str | None:
    if profile is None:
        return None
    text = " ".join(str(loc).lower() for loc in (getattr(profile, "locations", None) or []))
    for name, code in COUNTRY_CODE.items():
        if name in text:
            return code
    return None


def _remote_type(raw: dict) -> str | None:
    desc = str(raw.get("job_description") or "").lower()
    if "remote" in desc and "on-site" not in desc and "onsite" not in desc:
        return "remote"
    if "hybrid" in desc:
        return "hybrid"
    return None


def _to_int(value: object) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
