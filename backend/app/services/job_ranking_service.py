"""Explainable job ranking.

Ranking blends match score with freshness and job quality. A critical skill mismatch can
NOT be compensated by freshness — those jobs are ranked below any reasonably matching job.
"""

from __future__ import annotations

from app.services.job_freshness_service import Freshness
from app.services.job_match_service import MatchResult

FRESHNESS_BONUS = {
    Freshness.LAST_HOUR: 8,
    Freshness.LAST_24_HOURS: 6,
    Freshness.LAST_3_DAYS: 4,
    Freshness.LAST_7_DAYS: 2,
    Freshness.OLDER: 0,
    Freshness.UNKNOWN: 0,
}


def job_quality_score(
    *,
    description: str | None,
    salary_min: int | None,
    salary_max: int | None,
    location: str | None,
    skills_required: str | None,
    posting_verified: bool,
    remote_type: str | None = None,
) -> int:
    """0-100 data completeness score for a job listing."""
    score = 0
    if description and len(description) > 100:
        score += 25
    if salary_min is not None or salary_max is not None:
        score += 20
    if location:
        score += 15
    if skills_required:
        score += 15
    if posting_verified:
        score += 15
    if remote_type:
        score += 10
    return min(100, score)


def rank_score(match: MatchResult, freshness: Freshness, quality: int) -> tuple[int, str]:
    """Return (rank_score 0-100, human explanation)."""
    base = match.overall_score
    if base < 40:
        penalized = round(base * 0.6)
        return penalized, (
            f"Critical match gap ({match.critical_missing or match.missing_skills}) "
            f"keeps this job low despite freshness."
        )

    score = round(
        base
        + FRESHNESS_BONUS.get(freshness, 0)
        + (quality / 10)
    )
    score = max(0, min(100, score))
    explanation = (
        f"{base}% match + freshness {freshness.value.lower().replace('_', ' ')} "
        f"(+{FRESHNESS_BONUS.get(freshness, 0)}) + job quality {quality}"
    )
    return score, explanation
