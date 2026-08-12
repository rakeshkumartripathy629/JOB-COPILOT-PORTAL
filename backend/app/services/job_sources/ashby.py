"""Ashby public posting API source.

Uses Ashby's public ``posting-api`` endpoints for a curated set of orgs. No key required.
Ashby exposes the real posting time (``publishedAt``), which is used as the verified
``posted_at``.
"""

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

logger = logging.getLogger(__name__)

POSTING_API = "https://api.ashbyhq.com/posting-api/job-board/{org}"

#: Orgs verified to publish public job boards via Ashby (checked 2026-08).
ORGS = ["notion", "ramp", "ashby", "perplexity", "cursor", "zapier", "warp"]

COMPANY_NAMES = {
    "notion": "Notion",
    "ramp": "Ramp",
    "ashby": "Ashby",
    "perplexity": "Perplexity",
    "cursor": "Cursor",
    "zapier": "Zapier",
    "warp": "Warp",
}


class AshbySource(JobSource):
    name = "ashby"
    display_name = "Ashby"
    portal = "Ashby"
    source_method = SourceMethod.AUTHORIZED_FEED

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=20, min_interval=0.4, retries=1)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        tokens = _tokens(query)
        jobs: list[NormalizedJob] = []
        errors: list[str] = []
        for org in ORGS:
            try:
                resp = await self._client.get(POSTING_API.format(org=org))
            except SourceError as exc:
                errors.append(f"{org}: {exc.message}")
                continue
            if resp.status_code != 200:
                errors.append(f"{org}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            for item in data.get("jobs", []):
                if not item.get("isListed", True):
                    continue
                normalized = self.normalize_job(item, org)
                if not normalized or not self.validate_job(normalized):
                    continue
                if not tokens or _matches(normalized, tokens):
                    jobs.append(normalized)
                if len(jobs) >= 40:
                    break
            if len(jobs) >= 40:
                break
        if jobs:
            return SourceResult(SourceStatus.SUCCESS, jobs=jobs)
        if len(errors) == len(ORGS) and errors:
            return SourceResult(SourceStatus.ERROR, jobs=jobs, error="; ".join(errors[:3]))
        return SourceResult(SourceStatus.EMPTY, jobs=jobs, error="; ".join(errors[:3]) or None)

    def normalize_job(self, raw: dict, org: str = "") -> NormalizedJob | None:
        title = raw.get("title")
        url = raw.get("jobUrl") or raw.get("applyUrl")
        if not title or not url:
            return None
        location = raw.get("location")
        country = None
        if location:
            low = str(location).lower()
            for name in (
                "united states",
                "usa",
                "uk",
                "united kingdom",
                "germany",
                "canada",
                "australia",
                "india",
                "netherlands",
                "france",
                "spain",
                "portugal",
                "switzerland",
            ):
                if name in low:
                    country = "United States" if name == "usa" else ("United Kingdom" if name == "uk" else name.title())
                    break
        now = datetime.utcnow()
        return NormalizedJob(
            title=str(title),
            company=COMPANY_NAMES.get(org, org),
            location=location,
            country=country,
            remote_type=_remote_type(raw),
            employment_type=(raw.get("employmentType") or "").lower() or None,
            posted_at=_parse_dt(raw.get("publishedAt")),
            discovered_at=now,
            last_verified_at=now,
            source="Ashby",
            search_source="ashby",
            source_job_id=str(raw.get("id")) if raw.get("id") else None,
            source_url=str(url),
            canonical_url=str(url),
            application_url=raw.get("applyUrl") or str(url),
            source_metadata={"org": org, "department": raw.get("department")},
        )


def _tokens(query: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#.]+", query.lower()) if len(t) > 1}


def _matches(job: NormalizedJob, tokens: set[str]) -> bool:
    text = " ".join(filter(None, [job.title, job.location])).lower()
    return any(t in text for t in tokens)


def _remote_type(raw: dict) -> str | None:
    if raw.get("isRemote") is True:
        return "remote"
    workplace = str(raw.get("workplaceType") or "").lower()
    if "hybrid" in workplace:
        return "hybrid"
    if "on-site" in workplace or "onsite" in workplace:
        return "onsite"
    return None


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
