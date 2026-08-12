"""Central registry of job sources. New sources register here; the search engine is
unaware of specific implementations."""

from __future__ import annotations

import logging

from app.services.job_sources.base import JobSource

logger = logging.getLogger(__name__)


class JobSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, JobSource] = {}

    def register(self, source: JobSource) -> None:
        if source.name in self._sources:
            logger.warning("Overriding registered job source %r", source.name)
        self._sources[source.name] = source

    def get(self, name: str) -> JobSource | None:
        return self._sources.get(name)

    def all(self) -> list[JobSource]:
        return list(self._sources.values())

    def clear(self) -> None:
        self._sources.clear()


registry = JobSourceRegistry()


def register_all() -> None:
    """Register every built-in source once."""
    from app.services.job_sources.adzuna import AdzunaSource
    from app.services.job_sources.arbeitnow import ArbeitnowSource
    from app.services.job_sources.ashby import AshbySource
    from app.services.job_sources.google_cse import GoogleCseSource
    from app.services.job_sources.greenhouse import GreenhouseSource
    from app.services.job_sources.instahyre import InstahyreJobSource
    from app.services.job_sources.jsearch import JSearchSource
    from app.services.job_sources.linkedin import LinkedInJobSource
    from app.services.job_sources.naukri import NaukriJobSource
    from app.services.job_sources.remotive import RemotiveSource
    from app.services.job_sources.wellfound import WellfoundJobSource

    for source in (
        GoogleCseSource(),
        LinkedInJobSource(),
        WellfoundJobSource(),
        InstahyreJobSource(),
        NaukriJobSource(),
        AdzunaSource(),
        JSearchSource(),
        GreenhouseSource(),
        AshbySource(),
        RemotiveSource(),
        ArbeitnowSource(),
    ):
        registry.register(source)


# Register built-ins at import time so `registry.all()` always has them.
if not registry.all():
    register_all()
