import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMError, LLMService
from app.utils.document_utils import extract_text_from_path

logger = logging.getLogger(__name__)

MAX_RESUME_CHARS = 12000

PARSER_SYSTEM = (
    "You are an expert resume parser. Extract structured information from the raw resume text "
    "and return JSON with keys: designation (string, the most recent or primary job title/role "
    "from the resume, e.g. 'Backend Developer', 'Data Scientist'; omit seniority-only prefixes "
    "like 'Senior' when a clean title exists), summary (string), skills (list of strings), "
    "experience (list of strings), education (list of strings), certifications (list of strings)."
)

ATS_SYSTEM = (
    "You are an expert ATS (Applicant Tracking System) analyst. Score the resume for ATS "
    "friendliness (layout, keywords, sections, quantifiable achievements) and return JSON with "
    "keys: ats_score (integer 0-100), missing_keywords (list of strings)."
)

IMPROVER_SYSTEM = (
    "You are a senior career advisor. Return JSON with a single key 'suggestions' whose value is "
    "a list of concrete, actionable resume improvement suggestions."
)


class ResumeAgentState(TypedDict):
    db: AsyncSession
    resume_id: int
    file_path: str
    raw_text: str
    parsed_data: str
    ats_score: int
    missing_keywords: str
    suggestions: str
    error: str | None


def _serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _extract_text(state: ResumeAgentState):
    if state.get("raw_text"):
        return {"raw_text": state["raw_text"]}
    try:
        return {"raw_text": extract_text_from_path(state["file_path"])}
    except ValueError as e:
        logger.error("Resume text extraction failed: %s", e)
        return {"error": str(e), "raw_text": ""}


async def _parse_resume(state: ResumeAgentState):
    if state.get("error"):
        return {"parsed_data": state.get("parsed_data", "")}
    llm = LLMService()
    try:
        payload = await llm.generate_json(
            f"Resume text:\n{state['raw_text'][:MAX_RESUME_CHARS]}",
            system=PARSER_SYSTEM,
        )
        return {"parsed_data": _serialize(payload)}
    except LLMError as e:
        logger.warning("Resume parse failed: %s", e)
        return {"error": str(e)}


async def _analyze_ats(state: ResumeAgentState):
    if state.get("error"):
        return {"ats_score": state.get("ats_score", 0)}
    llm = LLMService()
    try:
        payload = await llm.generate_json(
            f"Resume text:\n{state['raw_text'][:MAX_RESUME_CHARS]}",
            system=ATS_SYSTEM,
        )
        raw_score = payload.get("ats_score", 0)
        try:
            score = max(0, min(100, int(float(raw_score))))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            score = 0
        missing = payload.get("missing_keywords", [])
        if not isinstance(missing, list):
            missing = []
        return {
            "ats_score": score,
            "missing_keywords": _serialize([str(k) for k in missing]),
        }
    except LLMError as e:
        logger.warning("ATS analysis failed: %s", e)
        return {"error": str(e)}


async def _suggest_improvements(state: ResumeAgentState):
    if state.get("error"):
        return {"suggestions": state.get("suggestions", "")}
    llm = LLMService()
    try:
        payload = await llm.generate_json(
            f"Resume text:\n{state['raw_text'][:MAX_RESUME_CHARS]}",
            system=IMPROVER_SYSTEM,
        )
        items = payload.get("suggestions", [])
        if not isinstance(items, list):
            items = []
        return {"suggestions": _serialize([str(s) for s in items])}
    except LLMError as e:
        logger.warning("Improvement suggestions failed: %s", e)
        return {"error": str(e)}


async def _persist(state: ResumeAgentState):
    from app.db.models.resume import Resume

    db = state["db"]
    result = await db.execute(select(Resume).where(Resume.id == state["resume_id"]))
    resume = result.scalar_one_or_none()
    if not resume:
        return {"error": state.get("error") or "Resume not found"}
    if state.get("parsed_data"):
        resume.parsed_data = state["parsed_data"]
    resume.ats_score = state.get("ats_score", 0)
    if state.get("missing_keywords"):
        resume.missing_keywords = state["missing_keywords"]
    if state.get("suggestions"):
        resume.improvement_suggestions = state["suggestions"]
    await db.commit()
    return {"ats_score": resume.ats_score}


workflow = StateGraph(ResumeAgentState)
workflow.add_node("extract_text", _extract_text)
workflow.add_node("parse_resume", _parse_resume)
workflow.add_node("analyze_ats", _analyze_ats)
workflow.add_node("suggest_improvements", _suggest_improvements)
workflow.add_node("persist", _persist)
workflow.set_entry_point("extract_text")
workflow.add_edge("extract_text", "parse_resume")
workflow.add_edge("parse_resume", "analyze_ats")
workflow.add_edge("analyze_ats", "suggest_improvements")
workflow.add_edge("suggest_improvements", "persist")
workflow.add_edge("persist", END)

resume_agent = workflow.compile()
