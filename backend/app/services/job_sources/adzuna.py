"""Adzuna job search API source.

Requires ADZUNA_APP_ID and ADZUNA_APP_KEY. Reports UNAVAILABLE when keys are missing.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.config import settings
from app.services.job_sources.base import JobSource, NormalizedJob, SourceError, SourceResult, SourceStatus
from app.services.job_sources.http import SourceHTTPClient
from app.utils.document_utils import html_to_text

logger = logging.getLogger(__name__)

ADZUNA_API_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

#: Adzuna region code -> country name.
COUNTRY_MAP = {
    "in": "India",
    "gb": "United Kingdom",
    "us": "United States",
    "de": "Germany",
    "ca": "Canada",
    "au": "Australia",
    "fr": "France",
    "nl": "Netherlands",
    "sg": "Singapore",
}


class AdzunaSource(JobSource):
    name = "adzuna"
    display_name = "Adzuna"
    portal = "Adzuna"

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=25, min_interval=1.5, retries=2)

    def is_available(self) -> bool:
        return bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        if not self.is_available():
            return SourceResult(
                SourceStatus.UNAVAILABLE,
                error="Adzuna unavailable: ADZUNA_APP_ID / ADZUNA_APP_KEY not configured.",
            )
        country = _pick_adzuna_country(profile)
        try:
            resp = await self._client.get(
                ADZUNA_API_URL.format(country=country),
                params={
                    "app_id": settings.ADZUNA_APP_ID,
                    "app_key": settings.ADZUNA_APP_KEY,
                    "results_per_page": 20,
                    "what": query,
                    "content-type": "application/json",
                    "max_days_old": 14,
                },
            )
        except SourceError as exc:
            return SourceResult(SourceStatus.ERROR, error=exc.message)
        if resp.status_code == 403:
            return SourceResult(SourceStatus.ERROR, error="Adzuna rejected the configured credentials (HTTP 403).")
        if resp.status_code == 429:
            return SourceResult(SourceStatus.RATE_LIMITED, error="Adzuna rate limited (HTTP 429).")
        if resp.status_code >= 400:
            return SourceResult(SourceStatus.ERROR, error=f"Adzuna returned HTTP {resp.status_code}.")
        data = resp.json()
        jobs = [n for item in data.get("results", []) if (n := self.normalize_job(item)) and self.validate_job(n)]
        if not jobs:
            return SourceResult(SourceStatus.EMPTY, jobs=jobs)
        return SourceResult(SourceStatus.SUCCESS, jobs=jobs)

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        title = raw.get("title")
        url = raw.get("redirect_url")
        if not title or not url:
            return None
        loc = (raw.get("location") or {}).get("display_name")
        company = (raw.get("company") or {}).get("display_name") or "Unknown"
        country = COUNTRY_MAP.get(raw.get("country", {}).get("code", "")) if isinstance(raw.get("country"), dict) else None
        now = datetime.utcnow()
        return NormalizedJob(
            title=str(title),
            company=company,
            description=html_to_text(raw.get("description")),
            location=loc,
            country=country,
            salary_min=_to_int(raw.get("salary_min")),
            salary_max=_to_int(raw.get("salary_max")),
            salary_currency=raw.get("salary_currency") or "GBP",
            posted_at=_parse_dt(raw.get("created")),
            discovered_at=now,
            last_verified_at=now,
            source="Adzuna",
            search_source="adzuna",
            source_job_id=str(raw.get("id")) if raw.get("id") is not None else None,
            source_url=str(url),
            canonical_url=str(url),
            application_url=str(url),
            employment_type=raw.get("contract_time"),
            source_metadata={"category": (raw.get("category") or {}).get("label") if isinstance(raw.get("category"), dict) else None},
        )


def _pick_adzuna_country(profile: object | None) -> str:
    if profile is None:
        return "gb"
    locations = getattr(profile, "locations", None) or []
    text = " ".join(str(loc).lower() for loc in locations)
    for code, name in COUNTRY_MAP.items():
        if name.lower() in text or code in text:
            return code
    return "gb"


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
