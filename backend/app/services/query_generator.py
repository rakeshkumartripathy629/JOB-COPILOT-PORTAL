"""Generate candidate search queries from a resume-derived SearchProfile.

Queries are combinations of roles and skills (e.g. "Backend Developer Node.js"), each
one grounded in resume evidence. The result is deduplicated and capped to keep external
source calls bounded.
"""

from __future__ import annotations

from app.services.search_profile_service import SearchProfile

MAX_QUERIES = 15
SKILLS_PER_ROLE = 6


def generate_queries(profile: SearchProfile, limit: int = MAX_QUERIES) -> list[str]:
    roles = [r for r in (profile.roles or []) if r.strip()]
    skills = [s for s in (profile.skills or []) if s.strip()][:10]
    queries: list[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = " ".join(query.split())
        key = q.casefold()
        if not q or len(q) > 120 or key in seen:
            return
        seen.add(key)
        queries.append(q)

    for role in roles[:4]:
        add(role)
    for role in roles[:4]:
        for skill in skills[:SKILLS_PER_ROLE]:
            add(f"{role} {skill}")
    if profile.seniority in ("Senior", "Staff", "Principal", "Lead"):
        for role in roles[:2]:
            add(f"Senior {role}")
    return queries[:limit]


def sample_queries(profile: SearchProfile) -> list[str]:
    """A compact representative set of queries used for display/status purposes."""
    return generate_queries(profile, limit=6)
