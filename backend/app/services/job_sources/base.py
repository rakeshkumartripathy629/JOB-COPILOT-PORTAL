"""Job source abstraction layer.

Every job source implements the :class:`JobSource` interface and is registered in
:class:`JobSourceRegistry`. New sources can be added without touching the search engine.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class SourceStatus(str, enum.Enum):
    SEARCHING = "SEARCHING"
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"


class SourceMethod(str, enum.Enum):
    """How a listing was obtained from its portal.

    OFFICIAL_API             — a documented portal API with credentials.
    AUTHORIZED_FEED          — a public/official feed or board API (no keys).
    PUBLIC_SEARCH_DISCOVERY  — found through a public search index (Google CSE),
                               never through the portal itself.
    PUBLIC_PAGE              — parsed directly from a public portal page.
    UNKNOWN                  — acquisition method not asserted.
    """

    OFFICIAL_API = "OFFICIAL_API"
    AUTHORIZED_FEED = "AUTHORIZED_FEED"
    PUBLIC_SEARCH_DISCOVERY = "PUBLIC_SEARCH_DISCOVERY"
    PUBLIC_PAGE = "PUBLIC_PAGE"
    UNKNOWN = "UNKNOWN"


class PostedAtPrecision(str, enum.Enum):
    """How exact the ``posted_at`` timestamp is.

    EXACT    — the portal exposed a concrete posting timestamp.
    RELATIVE — derived from a relative phrase ("2 days ago"); a real time, but fuzzy.
    UNKNOWN  — no posting time is available from the source.
    """

    EXACT = "EXACT"
    RELATIVE = "RELATIVE"
    UNKNOWN = "UNKNOWN"


class SourceError(Exception):
    """Base error raised by a job source."""

    status: SourceStatus = SourceStatus.ERROR

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class SourceUnavailable(SourceError):
    status = SourceStatus.UNAVAILABLE


class SourceRateLimited(SourceError):
    status = SourceStatus.RATE_LIMITED


@dataclass
class NormalizedJob:
    """The internal, source-agnostic representation of a job listing.

    ``source`` is the portal the job was found on (e.g. "LinkedIn", "Greenhouse").
    ``search_source`` is the mechanism that discovered it (e.g. "greenhouse", "google_cse").
    """

    title: str
    company: str
    source: str
    search_source: str
    description: str | None = None
    company_website: str | None = None
    location: str | None = None
    country: str | None = None
    city: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    skills: list[str] = field(default_factory=list)
    posted_at: datetime | None = None
    updated_at: datetime | None = None
    discovered_at: datetime | None = None
    last_verified_at: datetime | None = None
    source_job_id: str | None = None
    source_url: str | None = None
    canonical_url: str | None = None
    application_url: str | None = None
    is_active: bool = True
    source_metadata: dict[str, Any] = field(default_factory=dict)
    source_method: SourceMethod = SourceMethod.UNKNOWN
    source_portal: str | None = None
    posted_at_precision: PostedAtPrecision = PostedAtPrecision.UNKNOWN

    @property
    def posting_verified(self) -> bool:
        return self.posted_at is not None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for field_name in (
            "title",
            "company",
            "company_website",
            "location",
            "country",
            "city",
            "remote_type",
            "employment_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "description",
            "requirements",
            "responsibilities",
            "skills",
            "posted_at",
            "updated_at",
            "discovered_at",
            "last_verified_at",
            "source",
            "source_job_id",
            "source_url",
            "canonical_url",
            "application_url",
            "is_active",
            "search_source",
            "source_metadata",
            "source_method",
            "source_portal",
            "posted_at_precision",
        ):
            out[field_name] = getattr(self, field_name)
        return out


@dataclass
class SourceResult:
    status: SourceStatus
    jobs: list[NormalizedJob] = field(default_factory=list)
    error: str | None = None

    @property
    def count(self) -> int:
        return len(self.jobs)


class JobSource:
    """Abstract job source interface."""

    name: str = "base"
    display_name: str = "Base"
    portal: str = "Unknown"
    source_method: SourceMethod = SourceMethod.UNKNOWN

    #: Enable per-source call throttling / retries.
    timeout_seconds: float = 20.0
    retries: int = 2
    min_interval_seconds: float = 1.0

    def is_available(self) -> bool:
        """Whether this source is configured and can be queried right now."""
        return True

    async def search(self, query: str, profile: Any | None = None) -> SourceResult:
        """Search the source for ``query`` and return normalized results."""
        raise NotImplementedError

    async def get_job_details(self, job: NormalizedJob) -> NormalizedJob:
        """Best-effort enrichment of a single job's details. No-op by default."""
        return job

    def normalize_job(self, raw: Any) -> NormalizedJob | None:
        """Turn a raw source payload into a :class:`NormalizedJob`."""
        raise NotImplementedError

    def validate_job(self, job: NormalizedJob) -> bool:
        """Return True when the normalized job is complete enough to keep."""
        return bool(job.title and job.source_url and job.company)
