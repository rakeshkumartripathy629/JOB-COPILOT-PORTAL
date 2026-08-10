"""Canonicalization and deduplication of discovered jobs.

The same listing is frequently returned by multiple sources (or by the same source under
different queries). This module merges source occurrences into one canonical group using
URLs and a normalized title+company key, without discarding any real source reference.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.services.job_sources.base import NormalizedJob


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _norm_company(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (company or "").lower()).strip()


def _url_key(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    path = (parsed.path or "").rstrip("/").lower()
    host = (parsed.netloc or "").lower().replace("www.", "")
    return f"{host}{path}"


def canonical_key(job: NormalizedJob) -> str:
    return f"{_norm_title(job.title)}|{_norm_company(job.company)}"


def _richness(job: NormalizedJob) -> int:
    score = 0
    if job.description:
        score += 3
    if job.posted_at:
        score += 2
    if job.salary_min or job.salary_max:
        score += 2
    if job.location:
        score += 1
    if job.remote_type:
        score += 1
    if job.skills:
        score += 1
    return score


def _same_listing(a: NormalizedJob, b: NormalizedJob) -> bool:
    """True when two jobs point at the same underlying listing."""
    a_url = _url_key(a.canonical_url or a.source_url)
    b_url = _url_key(b.canonical_url or b.source_url)
    if a_url and b_url and a_url == b_url:
        return True
    a_id = (a.source or "").lower() + "|" + (a.source_job_id or "")
    b_id = (b.source or "").lower() + "|" + (b.source_job_id or "")
    if a.source_job_id and b.source_job_id and a_id == b_id:
        return True
    return bool(canonical_key(a)) and canonical_key(a) == canonical_key(b)


def canonicalize_jobs(jobs: list[NormalizedJob]) -> list[dict]:
    """Merge occurrences into canonical groups.

    Returns a list of ``{"job": NormalizedJob, "references": [NormalizedJob, ...]}`` where
    ``job`` is the richest occurrence and ``references`` hold every other source view.
    """
    groups: list[dict] = []

    def _find_group(job: NormalizedJob) -> dict | None:
        for group in groups:
            if _same_listing(group["job"], job):
                return group
        return None

    for job in jobs:
        group = _find_group(job)
        if group is None:
            groups.append({"job": job, "references": []})
        elif _richness(job) > _richness(group["job"]):
            group["references"].append(group["job"])
            group["job"] = job
        else:
            group["references"].append(job)

    return groups
