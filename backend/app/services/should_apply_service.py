"""ShouldApply: should this user apply to this job?

A deterministic recommendation built only from real signals (evidence-based match,
critical gaps, confidence). Never guesses: gaps and reasons are grounded in the
requirement matrix.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.services.advanced_match_service import AdvancedMatch

STRONGLY_RECOMMENDED = "STRONGLY_RECOMMENDED"
RECOMMENDED = "RECOMMENDED"
CONSIDER = "CONSIDER"
LOW_PRIORITY = "LOW_PRIORITY"
SKIP = "SKIP"


@dataclass
class ShouldApplyResult:
    decision: str
    confidence: int
    recommendation: str
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    critical_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def decide_should_apply(match: AdvancedMatch) -> ShouldApplyResult:
    overall = match.overall_score
    confidence = match.match_confidence
    critical = match.critical_missing

    if overall >= 80 and not critical and confidence >= 70:
        decision = STRONGLY_RECOMMENDED
    elif overall >= 65 and not critical:
        decision = RECOMMENDED
    elif overall >= 50 and len(critical) <= 1:
        decision = CONSIDER
    elif overall >= 35 and len(critical) <= 2:
        decision = LOW_PRIORITY
    else:
        decision = SKIP

    reasons: list[str] = []
    risks: list[str] = []

    if match.required_skill_score >= 80:
        reasons.append("Strong evidence for the required skills.")
    elif match.required_skill_score >= 55:
        reasons.append("Partial evidence for the required skills.")
    if match.experience_score >= 80:
        reasons.append("Your experience fits the role's experience band.")
    if match.location_score >= 85:
        reasons.append("Location / remote setup works for you.")
    if match.education_score >= 90:
        reasons.append("Education requirement is met.")
    if match.career_goal_score >= 80:
        reasons.append("The role aligns with your target roles.")
    if confidence >= 80:
        reasons.append("High confidence: most matched facts are verified.")
    if not reasons:
        reasons.append("Limited direct evidence between your profile and this job.")

    if critical:
        risks.append("Missing critical requirement(s): " + ", ".join(critical[:5]) + ".")
    if match.required_skill_score < 50:
        risks.append("Little direct evidence for the job's required skills.")
    if match.education_score < 40 and any(m["requirement"] == "degree" for m in match.requirements):
        risks.append("No education evidence for the degree requirement.")
    if confidence < 50:
        risks.append("Low confidence: resume evidence is sparse or unverified.")
    if not risks:
        risks.append("No significant risks detected.")

    label = {
        STRONGLY_RECOMMENDED: "Strongly recommended — you are a strong candidate for this role.",
        RECOMMENDED: "Recommended — solid evidence of a good fit.",
        CONSIDER: "Consider applying — there is a reasonable fit, but review the gaps first.",
        LOW_PRIORITY: "Low priority — apply only if this role is otherwise attractive to you.",
        SKIP: "Skip — the evidence does not support applying to this role right now.",
    }[decision]

    return ShouldApplyResult(
        decision=decision,
        confidence=confidence,
        recommendation=label,
        reasons=reasons,
        risks=risks,
        critical_gaps=critical,
    )
