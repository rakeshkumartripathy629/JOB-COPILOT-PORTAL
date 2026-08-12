"""Arbeitnow job board API source (public, no key required)."""

from __future__ import annotations

import logging
import re
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

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(JobSource):
    name = "arbeitnow"
    display_name = "Arbeitnow"
    portal = "Arbeitnow"
    source_method = SourceMethod.AUTHORIZED_FEED

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=25, min_interval=1.0, retries=2)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        try:
            resp = await self._client.get(ARBEITNOW_URL, params={"limit": 50})
        except SourceError as exc:
            return SourceResult(SourceStatus.ERROR, error=exc.message)
        if resp.status_code == 429:
            return SourceResult(SourceStatus.RATE_LIMITED, error="Arbeitnow rate limited (HTTP 429).")
        if resp.status_code >= 400:
            return SourceResult(SourceStatus.ERROR, error=f"Arbeitnow returned HTTP {resp.status_code}.")
        data = resp.json()
        tokens = _tokens(query)
        jobs: list[NormalizedJob] = []
        for item in data.get("data", []):
            normalized = self.normalize_job(item)
            if not normalized or not self.validate_job(normalized):
                continue
            if not tokens or _matches(normalized, tokens):
                jobs.append(normalized)
            if len(jobs) >= 40:
                break
        if not jobs:
            return SourceResult(SourceStatus.EMPTY, jobs=jobs)
        return SourceResult(SourceStatus.SUCCESS, jobs=jobs)

    def normalize_job(self, raw: dict) -> NormalizedJob | None:
        title = raw.get("title")
        url = raw.get("url")
        if not title or not url:
            return None
        location = raw.get("location") or ""
        remote = bool(raw.get("remote"))
        now = datetime.utcnow()
        return NormalizedJob(
            title=str(title),
            company=(raw.get("company_name") or "Unknown"),
            description=html_to_text(raw.get("description")),
            location=location or ("Remote" if remote else "Germany"),
            country=None,
            remote_type="remote" if remote else ("hybrid" if "hybrid" in str(raw.get("job_types", [])).lower() else None),
            salary_min=_parse_salary(raw.get("salary") or ""),
            salary_max=None,
            salary_currency="EUR",
            posted_at=_parse_dt(raw.get("created_at")),
            discovered_at=now,
            last_verified_at=now,
            source="Arbeitnow",
            search_source="arbeitnow",
            source_url=str(url),
            canonical_url=str(url),
            application_url=str(url),
            source_metadata={"tags": raw.get("tags"), "job_types": raw.get("job_types")},
        )


def _parse_salary(text: str) -> int | None:
    nums = [int(n) for n in re.findall(r"\d{3,}", text.replace(",", ""))]
    return nums[0] if nums else None


def _tokens(query: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#.]+", query.lower()) if len(t) > 1}


def _matches(job: NormalizedJob, tokens: set[str]) -> bool:
    text = " ".join(filter(None, [job.title, job.location])).lower()
    return any(t in text for t in tokens)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
