import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.application import (
    RESPONSE_STATUSES,
    Application,
    ApplicationStatus,
)
from app.db.models.cover_letter import CoverLetter
from app.db.models.interview_question import InterviewQuestion
from app.db.models.notification import Notification
from app.db.models.resume import Resume
from app.db.models.resume_version import ResumeVersion
from app.services.llm_service import LLMError, LLMService

logger = logging.getLogger(__name__)

INSIGHTS_SYSTEM = (
    "You are a data-savvy career strategist. From the user's job-search metrics, return JSON "
    "with a single key 'insights' whose value is a list of 2-5 short, actionable observations."
)


class AnalyticsAgentState(TypedDict):
    db: AsyncSession
    user_id: int
    metrics: dict[str, Any]
    insights: list[str]


async def _aggregate_metrics(state: AnalyticsAgentState):
    db = state["db"]
    user_id = state["user_id"]

    total_apps = await db.execute(select(func.count(Application.id)).where(Application.user_id == user_id))
    total_applications = total_apps.scalar_one() or 0

    by_status: dict[str, int] = {}
    status_rows = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == user_id)
        .group_by(Application.status)
    )
    for status, count in status_rows.all():
        by_status[status.value if hasattr(status, "value") else str(status)] = count

    interviews = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == user_id,
            Application.status.in_([ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER]),
        )
    )
    cover_letters = await db.execute(select(func.count(CoverLetter.id)).where(CoverLetter.user_id == user_id))
    resumes = await db.execute(select(func.count(Resume.id)).where(Resume.user_id == user_id))
    resume_versions = await db.execute(select(func.count(ResumeVersion.id)).where(ResumeVersion.user_id == user_id))
    notifications = await db.execute(select(func.count(Notification.id)).where(Notification.user_id == user_id))
    unread = await db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read == 0)
    )
    avg_ats = await db.execute(select(func.avg(Resume.ats_score)).where(Resume.user_id == user_id))
    avg_ats_value = avg_ats.scalar_one()
    questions = await db.execute(select(func.count(InterviewQuestion.id)).where(InterviewQuestion.user_id == user_id))

    submitted = total_applications - by_status.get("DRAFT", 0)
    response_count = sum(by_status.get(s.value, 0) for s in RESPONSE_STATUSES)
    response_rate = round(response_count / submitted * 100) if submitted else 0

    metrics = {
        "total_applications": total_applications,
        "applications_by_status": by_status,
        "interviews": interviews.scalar_one() or 0,
        "response_rate_percent": response_rate,
        "cover_letters": cover_letters.scalar_one() or 0,
        "resumes": resumes.scalar_one() or 0,
        "resume_versions": resume_versions.scalar_one() or 0,
        "interview_questions_prepared": questions.scalar_one() or 0,
        "notifications_total": notifications.scalar_one() or 0,
        "notifications_unread": unread.scalar_one() or 0,
        "average_ats_score": round(float(avg_ats_value), 1) if avg_ats_value else None,
    }
    return {"metrics": metrics}


async def _analyze_trends(state: AnalyticsAgentState):
    metrics = state.get("metrics") or {}
    insights = []
    if metrics.get("total_applications", 0) == 0:
        insights = [
            "Start applying by saving jobs and tracking applications to see patterns here.",
            "Upload a resume to unlock ATS scoring and match insights.",
        ]
        return {"insights": insights}

    llm = LLMService()
    try:
        payload = await llm.generate_json(
            f"Metrics:\n{metrics}",
            system=INSIGHTS_SYSTEM,
        )
        raw = payload.get("insights", [])
        if isinstance(raw, list):
            insights = [str(i) for i in raw]
    except LLMError:
        logger.warning("Insight generation failed; using generic insights")
        insights = [
            f"You have {metrics.get('total_applications', 0)} applications tracked with "
            f"{metrics.get('interviews', 0)} interviews.",
        ]
    if not insights:
        insights = ["Keep applying consistently and follow up on pending applications."]
    return {"insights": insights}


workflow = StateGraph(AnalyticsAgentState)
workflow.add_node("aggregate_metrics", _aggregate_metrics)
workflow.add_node("analyze_trends", _analyze_trends)
workflow.set_entry_point("aggregate_metrics")
workflow.add_edge("aggregate_metrics", "analyze_trends")
workflow.add_edge("analyze_trends", END)

analytics_agent = workflow.compile()
