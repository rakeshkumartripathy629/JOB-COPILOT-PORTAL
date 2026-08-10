"""Portal identification from job URLs.

Determines which portal a listing belongs to from its URL/domain. Never guesses: if the
domain cannot be classified it returns "Unknown" (or "Company Website" for obvious
career-page patterns).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

PORTAL_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(^|\.)linkedin\.com$"), "LinkedIn"),
    (re.compile(r"(^|\.)indeed\.com$"), "Indeed"),
    (re.compile(r"(^|\.)naukri\.com$"), "Naukri"),
    (re.compile(r"(^|\.)wellfound\.com$"), "Wellfound"),
    (re.compile(r"(^|\.)boards\.greenhouse\.io$"), "Greenhouse"),
    (re.compile(r"(^|\.)job-boards\.greenhouse\.io$"), "Greenhouse"),
    (re.compile(r"(^|\.)jobs\.ashbyhq\.com$"), "Ashby"),
    (re.compile(r"(^|\.)lever\.co$"), "Lever"),
    (re.compile(r"(^|\.)ziprecruiter\.com$"), "ZipRecruiter"),
    (re.compile(r"(^|\.)monster\.com$"), "Monster"),
    (re.compile(r"(^|\.)dice\.com$"), "Dice"),
    (re.compile(r"(^|\.)glassdoor\.com$"), "Glassdoor"),
    (re.compile(r"(^|\.)adzuna\.(com|co\.uk|de|in|ca|au|br|fr|nl|sg|es|it|pl)$"), "Adzuna"),
    (re.compile(r"(^|\.)remotive\.com$"), "Remotive"),
    (re.compile(r"(^|\.)arbeitnow\.com$"), "Arbeitnow"),
]

CAREER_PATH = re.compile(r"^/(careers?|jobs|job|openings|join-us)", re.IGNORECASE)


def identify_portal(url: str | None) -> str:
    """Map a job URL to a human-readable portal name."""
    if not url:
        return "Unknown"
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().strip(".")
    except ValueError:
        return "Unknown"
    if not host:
        return "Unknown"
    for pattern, name in PORTAL_RULES:
        if pattern.search(host):
            return name
    # Company career pages: careers.<company>.com, <company>.jobs, /careers/ path...
    if host.startswith("careers.") or host.startswith("jobs."):
        return "Company Website"
    if host.endswith(".jobs"):
        return "Company Website"
    if CAREER_PATH.match(parsed.path or ""):
        return "Company Website"
    return "Unknown"
