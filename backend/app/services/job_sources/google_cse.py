"""Google Programmable Search (CSE) discovery source.

Discovers job listings on job portals through the Custom Search JSON API using
portal-specific ``site:`` operators. Google is treated as a *discovery* source only:
we never claim every listing is present, and portal/timestamps come from the real
target pages, never from Google's index metadata.

If the configured API key is not authorized for the Custom Search JSON API, the source
reports UNAVAILABLE with the provider's real error message.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.config import settings
from app.services.job_sources.base import JobSource, NormalizedJob, SourceError, SourceResult, SourceStatus
from app.services.job_sources.http import SourceHTTPClient
from app.services.job_sources.portal import identify_portal

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

#: site: operators for portals that do not expose a permitted direct integration.
PORTAL_OPERATORS: list[tuple[str, str]] = [
    ("LinkedIn", "site:linkedin.com/jobs"),
    ("Indeed", "site:indeed.com/viewjob"),
    ("Naukri", "site:naukri.com/job-listings"),
    ("Wellfound", "site:wellfound.com/jobs"),
    ("Greenhouse", "site:boards.greenhouse.io"),
    ("Ashby", "site:jobs.ashbyhq.com"),
]

#: Max Custom Search API calls per search() invocation (quota is typically 100/day).
MAX_CALLS = 6


class GoogleCseSource(JobSource):
    name = "google_cse"
    display_name = "Google Search"
    portal = "Google Search"

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=20, min_interval=1.0, retries=1)

    def is_available(self) -> bool:
        return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        if not self.is_available():
            return SourceResult(
                SourceStatus.UNAVAILABLE,
                error="Google Search unavailable: Custom Search API key/CSE id not configured.",
            )
        jobs: list[NormalizedJob] = []
        # Round-robin over portal-specific searches so quota is spread across portals.
        calls: list[str] = [f'"{query}"']
        for _operator, operator in PORTAL_OPERATORS:
            calls.append(f'{operator} "{query}"')
        for index in range(MAX_CALLS):
            full_query = calls[index % len(calls)]
            try:
                resp = await self._client.get(
                    SEARCH_URL,
                    params={"key": settings.GOOGLE_API_KEY, "cx": settings.GOOGLE_CSE_ID, "q": full_query, "num": 5},
                )
            except SourceError as exc:
                return SourceResult(SourceStatus.ERROR, jobs=jobs, error=exc.message)
            if resp.status_code == 403:
                return SourceResult(
                    SourceStatus.UNAVAILABLE,
                    jobs=jobs,
                    error="Google Search unavailable: Custom Search JSON API is not enabled for the configured key.",
                )
            if resp.status_code == 429:
                return SourceResult(SourceStatus.RATE_LIMITED, jobs=jobs, error="Google Search rate limited (HTTP 429).")
            if resp.status_code >= 400:
                return SourceResult(
                    SourceStatus.ERROR, jobs=jobs, error=f"Google Search returned HTTP {resp.status_code}."
                )
            data = resp.json()
            for item in data.get("items", []):
                normalized = self.normalize_job(item)
                if normalized and self.validate_job(normalized):
                    jobs.append(normalized)
        if jobs:
            return SourceResult(SourceStatus.SUCCESS, jobs=jobs)
        return SourceResult(SourceStatus.EMPTY, jobs=jobs)

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        link = raw.get("link")
        title = raw.get("title")
        if not title or not link:
            return None
        now = datetime.utcnow()
        portal = identify_portal(link)
        return NormalizedJob(
            title=str(title)[:255],
            company=_company_hint(link, raw),
            description=raw.get("snippet"),
            source=portal,
            search_source="google_cse",
            source_url=str(link),
            canonical_url=str(link),
            discovered_at=now,
            last_verified_at=now,
            posted_at=None,
            source_metadata={"google_result": True, "portal_query": raw.get("title", "")},
        )


def _company_hint(url: str, raw: dict) -> str:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).netloc or ""
    except ValueError:
        host = ""
    label = host
    if label.startswith("www."):
        label = label[4:]
    label = label.split(".")[0]
    return label or "Unknown"
