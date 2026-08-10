"""Greenhouse public boards API source.

Uses Greenhouse's free, public ``boards-api.greenhouse.io`` endpoints for a curated set
of companies. No key required; respects Greenhouse's public terms of use.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from app.services.job_sources.base import JobSource, NormalizedJob, SourceError, SourceResult, SourceStatus
from app.services.job_sources.http import SourceHTTPClient

logger = logging.getLogger(__name__)

BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

#: Companies verified to publish public job boards via Greenhouse (checked 2026-08).
BOARDS = [
    "stripe",
    "datadog",
    "coinbase",
    "twilio",
    "reddit",
    "instacart",
    "robinhood",
    "dropbox",
    "pinterest",
    "figma",
    "monzo",
    "mixpanel",
]

COMPANY_NAMES = {
    "stripe": "Stripe",
    "datadog": "Datadog",
    "coinbase": "Coinbase",
    "twilio": "Twilio",
    "reddit": "Reddit",
    "instacart": "Instacart",
    "robinhood": "Robinhood",
    "dropbox": "Dropbox",
    "pinterest": "Pinterest",
    "figma": "Figma",
    "monzo": "Monzo",
    "mixpanel": "Mixpanel",
}


class GreenhouseSource(JobSource):
    name = "greenhouse"
    display_name = "Greenhouse"
    portal = "Greenhouse"

    def __init__(self) -> None:
        self._client = SourceHTTPClient(timeout=20, min_interval=0.4, retries=1)

    async def search(self, query: str, profile: object | None = None) -> SourceResult:
        tokens = _tokens(query)
        jobs: list[NormalizedJob] = []
        errors: list[str] = []
        for board in BOARDS:
            try:
                resp = await self._client.get(BOARDS_API.format(board=board))
            except SourceError as exc:
                errors.append(f"{board}: {exc.message}")
                continue
            if resp.status_code != 200:
                errors.append(f"{board}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            for item in data.get("jobs", []):
                normalized = self.normalize_job(item, board)
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
        if len(errors) == len(BOARDS) and errors:
            return SourceResult(SourceStatus.ERROR, jobs=jobs, error="; ".join(errors[:3]))
        return SourceResult(SourceStatus.EMPTY, jobs=jobs, error="; ".join(errors[:3]) or None)

    def normalize_job(self, raw: dict, board: str = "") -> NormalizedJob | None:
        title = raw.get("title")
        url = raw.get("absolute_url")
        if not title or not url:
            return None
        loc = (raw.get("location") or {}).get("name")
        updated = _parse_dt(raw.get("updated_at"))
        now = datetime.utcnow()
        return NormalizedJob(
            title=str(title),
            company=COMPANY_NAMES.get(board, board),
            location=loc,
            country=_country_from_location(loc),
            remote_type=_remote_from_location(loc),
            employment_type=(raw.get("employment_type") or "").lower() or None,
            updated_at=updated,
            posted_at=None,
            discovered_at=now,
            last_verified_at=now,
            source="Greenhouse",
            search_source="greenhouse",
            source_job_id=str(raw.get("id")) if raw.get("id") is not None else None,
            source_url=str(url),
            canonical_url=str(url),
            application_url=str(url),
            source_metadata={"board": board, "department": (raw.get("department") or {}).get("name")},
        )


def _tokens(query: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#.]+", query.lower()) if len(t) > 1}


def _matches(job: NormalizedJob, tokens: set[str]) -> bool:
    text = " ".join(filter(None, [job.title, job.location])).lower()
    return any(t in text for t in tokens)


def _country_from_location(loc: str | None) -> str | None:
    if not loc:
        return None
    low = loc.lower()
    for country in (
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
        "ireland",
        "sweden",
        "singapore",
    ):
        if country in low:
            return "United States" if country == "usa" else ("United Kingdom" if country == "uk" else country.title())
    return None


def _remote_from_location(loc: str | None) -> str | None:
    if not loc:
        return None
    low = loc.lower()
    if "remote" in low:
        return "remote"
    if "hybrid" in low:
        return "hybrid"
    return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
