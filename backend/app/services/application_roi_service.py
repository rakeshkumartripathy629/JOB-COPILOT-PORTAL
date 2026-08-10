"""ApplicationROI: estimated return on applying to a job.

Computed from real signals only — evidence-based match, salary band, posting quality,
freshness, and the ShouldApply decision. When salary data is missing the estimate is
labelled as approximate; ROI is never fabricated from historical application data that
does not exist.
"""

from __future__ import annotations

from app.services.advanced_match_service import AdvancedMatch
from app.services.job_freshness_service import Freshness
from app.services.should_apply_service import (
    CONSIDER,
    LOW_PRIORITY,
    RECOMMENDED,
    SKIP,
    STRONGLY_RECOMMENDED,
    ShouldApplyResult,
)

_DECISION_WEIGHT = {
    STRONGLY_RECOMMENDED: 100,
    RECOMMENDED: 85,
    CONSIDER: 70,
    LOW_PRIORITY: 50,
    SKIP: 20,
}

_FRESHNESS_WEIGHT = {
    Freshness.LAST_HOUR.value: 95,
    Freshness.LAST_24_HOURS.value: 85,
    Freshness.LAST_3_DAYS.value: 75,
    Freshness.LAST_7_DAYS.value: 60,
    Freshness.OLDER.value: 35,
    Freshness.UNKNOWN.value: 50,
    None: 50,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> int:
    return max(int(low), min(int(high), round(value)))


def compute_application_roi(
    match: AdvancedMatch,
    should_apply: ShouldApplyResult,
    *,
    salary_min: int | None = None,
    salary_max: int | None = None,
    salary_currency: str | None = "USD",
    job_quality_score: int | None = None,
    freshness: str | None = None,
) -> dict:
    has_salary = bool(salary_min is not None and salary_max is not None and salary_max > (salary_min or 0))
    if has_salary:
        estimated_salary: int | None = round(((salary_min or 0) + (salary_max or 0)) / 2)
        salary_score = 80 if (salary_max or 0) - (salary_min or 0) >= 20000 else 70
        salary_confidence = 85
    elif salary_min is not None or salary_max is not None:
        estimated_salary = salary_min or salary_max
        salary_score = 45
        salary_confidence = 45
    else:
        estimated_salary = None
        salary_score = 40
        salary_confidence = 0

    quality = job_quality_score if job_quality_score is not None else 50
    quality = _clamp(quality)
    freshness_score = _FRESHNESS_WEIGHT.get(freshness, 50)
    decision_weight = _DECISION_WEIGHT.get(should_apply.decision, 50)

    roi_score = _clamp(
        0.35 * match.overall_score
        + 0.20 * salary_score
        + 0.15 * quality
        + 0.15 * freshness_score
        + 0.15 * decision_weight
    )

    notes: list[str] = []
    if not has_salary:
        notes.append("Salary band not published; ROI uses skills fit, quality and freshness only.")
    if job_quality_score is None:
        notes.append("Posting quality score is not available for this job.")
    if match.match_confidence < 50:
        notes.append("Match confidence is low; verify your resume evidence in the Career Vault.")

    if not notes:
        notes.append("Estimate uses published salary, posting quality and freshness signals.")

    return {
        "roi_score": roi_score,
        "decision": should_apply.decision,
        "estimated_salary": estimated_salary,
        "salary_currency": salary_currency,
        "salary_confidence": salary_confidence,
        "signals": {
            "match_score": match.overall_score,
            "salary_score": salary_score,
            "job_quality_score": quality,
            "freshness_score": freshness_score,
            "decision_score": decision_weight,
        },
        "notes": notes,
    }
