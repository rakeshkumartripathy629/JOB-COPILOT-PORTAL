"""Remotive remote jobs API source (public, no key required)."""

from __future__ import annotations

import logging
from datetime import datetime

from app.services.job_sources.base import (
    JobSource,
    NormalizedJob,
    SourceError,
    SourceMethod,
    SourceResult,
    SourceStatus,
)
from app.services.job_sources.http import SourceHTTPClient
from app.utils.document_utils import html_to_text

logger = logging.getLogger(__name__)

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


class RemotiveSource(JobSource):
    name = "remotive"
    display_name = "Remotive"
    portal = "Remotive"
    source_method = SourceMethod.AUTHORIZED_FEED

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=25, min_interval=1.0, retries=2)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        try:
            resp = await self._client.get(REMOTIVE_URL, params={"limit": 100, "search": query})
        except SourceError as exc:
            return SourceResult(SourceStatus.ERROR, error=exc.message)
        if resp.status_code == 429:
            return SourceResult(SourceStatus.RATE_LIMITED, error="Remotive rate limited (HTTP 429).")
        if resp.status_code >= 400:
            return SourceResult(SourceStatus.ERROR, error=f"Remotive returned HTTP {resp.status_code}.")
        data = resp.json()
        jobs = [n for item in data.get("jobs", []) if (n := self.normalize_job(item)) and self.validate_job(n)]
        if not jobs:
            return SourceResult(SourceStatus.EMPTY, jobs=jobs)
        return SourceResult(SourceStatus.SUCCESS, jobs=jobs)

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        title = raw.get("title")
        url = raw.get("url")
        if not title or not url:
            return None
        location = raw.get("candidate_required_location") or "Remote"
        now = datetime.utcnow()
        return NormalizedJob(
            title=str(title),
            company=(raw.get("company_name") or "Unknown"),
            description=html_to_text(raw.get("description")),
            location=location,
            country="United States" if location.lower().startswith("usa") else None,
            remote_type="remote",
            posted_at=_parse_dt(raw.get("publication_date")),
            discovered_at=now,
            last_verified_at=now,
            source="Remotive",
            search_source="remotive",
            source_url=str(url),
            canonical_url=str(url),
            application_url=str(url),
            source_metadata={"category": raw.get("category"), "tags": raw.get("tags")},
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
