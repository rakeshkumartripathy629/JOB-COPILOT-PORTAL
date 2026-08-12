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
from app.services.job_sources.base import (
    JobSource,
    NormalizedJob,
    PostedAtPrecision,
    SourceError,
    SourceMethod,
    SourceResult,
    SourceStatus,
)
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
    source_method = SourceMethod.PUBLIC_SEARCH_DISCOVERY

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=20, min_interval=1.0, retries=1)

    def is_available(self) -> bool:
        return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID)

    def requires_config(self) -> list[str]:
        missing = []
        if not settings.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if not settings.GOOGLE_CSE_ID:
            missing.append("GOOGLE_CSE_ID")
        return missing

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
            source_portal=portal,
            search_source="google_cse",
            source_url=str(link),
            canonical_url=str(link),
            discovered_at=now,
            last_verified_at=now,
            posted_at=None,
            posted_at_precision=PostedAtPrecision.UNKNOWN,
            source_method=SourceMethod.PUBLIC_SEARCH_DISCOVERY,
            source_metadata={"google_result": True, "portal_query": raw.get("title", "")},
        )


class GoogleCsePortalSource(JobSource):
    """A single-portal job source backed by Google Custom Search.

    Each portal that has no direct integration gets its own dedicated source that
    scopes a Google CSE query with a ``site:`` operator. Google is only a discovery
    index: timestamps and details come from the real portal pages, never invented.
    """

    name: str = "google_cse_portal"
    display_name: str = "Portal"
    portal: str = "Unknown"
    site_operator: str = ""
    source_method = SourceMethod.PUBLIC_SEARCH_DISCOVERY
    #: How many results to request per CSE call (quota is typically 100/day).
    num_results: int = 10

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=20, min_interval=1.0, retries=1)

    def is_available(self) -> bool:
        return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_CSE_ID)

    def requires_config(self) -> list[str]:
        missing = []
        if not settings.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if not settings.GOOGLE_CSE_ID:
            missing.append("GOOGLE_CSE_ID")
        return missing

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        if not self.is_available():
            return SourceResult(
                SourceStatus.UNAVAILABLE,
                error=f"{self.portal} unavailable: Custom Search API key/CSE id not configured.",
            )
        if not self.site_operator:
            return SourceResult(SourceStatus.ERROR, error=f"{self.portal} source is not configured.")
        full_query = f'{self.site_operator} "{query}"'
        try:
            resp = await self._client.get(
                SEARCH_URL,
                params={
                    "key": settings.GOOGLE_API_KEY,
                    "cx": settings.GOOGLE_CSE_ID,
                    "q": full_query,
                    "num": self.num_results,
                },
            )
        except SourceError as exc:
            return SourceResult(SourceStatus.ERROR, error=exc.message)
        if resp.status_code == 403:
            return SourceResult(
                SourceStatus.UNAVAILABLE,
                error="Google Search unavailable: Custom Search JSON API is not enabled for the configured key.",
            )
        if resp.status_code == 429:
            return SourceResult(SourceStatus.RATE_LIMITED, error="Google Search rate limited (HTTP 429).")
        if resp.status_code >= 400:
            return SourceResult(SourceStatus.ERROR, error=f"Google Search returned HTTP {resp.status_code}.")
        jobs: list[NormalizedJob] = []
        for item in resp.json().get("items", []):
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
        return NormalizedJob(
            title=str(title)[:255],
            company=_company_hint(link, raw),
            description=raw.get("snippet"),
            source=self.portal,
            source_portal=self.portal,
            search_source=self.name,
            source_url=str(link),
            canonical_url=str(link),
            discovered_at=now,
            last_verified_at=now,
            posted_at=None,
            posted_at_precision=PostedAtPrecision.UNKNOWN,
            source_method=SourceMethod.PUBLIC_SEARCH_DISCOVERY,
            source_metadata={"google_result": True, "site_operator": self.site_operator},
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
