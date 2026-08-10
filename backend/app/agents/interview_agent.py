import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job
from app.services.llm_service import LLMError, LLMService

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = ["technical", "behavioral"]

JD_SYSTEM = (
    "You are a technical recruiter. From a job description, return JSON with a key "
    "'categories' whose value is a list of 1-3 interview categories chosen from: "
    "hr, technical, js, react, node, python, sql, behavioral."
)

QUESTIONS_SYSTEM = (
    "You are an interview coach. For the given role and category, return JSON with a key "
    "'questions' whose value is an array of objects with keys: question, explanation."
)

ANSWERS_SYSTEM = (
    "You are a senior engineer helping a candidate prepare. For each question, return JSON with "
    "a key 'answers' whose value is an array of objects with keys: index (integer matching the "
    "input order), suggested_answer. Keep answers concise and structured."
)


class InterviewAgentState(TypedDict):
    db: AsyncSession
    user_id: int
    job_id: int
    categories: list[str]
    questions: list[dict[str, Any]]


async def _analyze_jd(state: InterviewAgentState):
    db = state["db"]
    result = await db.execute(select(Job, Company).join(Company).where(Job.id == state["job_id"]))
    row = result.first()
    if not row:
        return {"questions": []}
    job, _ = row
    categories = state.get("categories") or []
    if categories:
        return {"categories": categories}
    llm = LLMService()
    try:
        payload = await llm.generate_json(
            f"Job title: {job.title}\nJob description: {job.description or 'Not provided'}",
            system=JD_SYSTEM,
        )
        raw = payload.get("categories", [])
        if not isinstance(raw, list):
            raw = []
        categories = [str(c).strip().lower() for c in raw][:3]
        valid = {"hr", "technical", "js", "react", "node", "python", "sql", "behavioral"}
        categories = [c for c in categories if c in valid] or DEFAULT_CATEGORIES
    except LLMError:
        logger.warning("Job description analysis failed; using defaults")
        categories = DEFAULT_CATEGORIES
    return {"categories": categories}


async def _generate_questions(state: InterviewAgentState):
    db = state["db"]
    result = await db.execute(select(Job, Company).join(Company).where(Job.id == state["job_id"]))
    row = result.first()
    if not row:
        return {"questions": state.get("questions", [])}
    job, _ = row
    categories = state.get("categories") or DEFAULT_CATEGORIES

    items: list[dict[str, Any]] = []
    llm = LLMService()
    for category in categories:
        prompt = (
            f"Generate 5 interview questions for the role of {job.title}.\n"
            f"Category: {category}\n"
            f"Job description: {job.description or 'Not provided'}\n\n"
            "Return a JSON object with a key 'questions' whose value is an array of objects with "
            "keys: question, explanation."
        )
        payload = await llm.generate_json(prompt, system=QUESTIONS_SYSTEM)
        raw = payload.get("questions", [])
        if not isinstance(raw, list):
            raw = payload.get("items", [])
        if not isinstance(raw, list):
            raw = []
        for entry in raw:
            if not isinstance(entry, dict) or not entry.get("question"):
                continue
            items.append(
                {
                    "category": category,
                    "question": str(entry["question"]),
                    "explanation": entry.get("explanation"),
                    "suggested_answer": None,
                }
            )
    return {"questions": items}


async def _generate_answers(state: InterviewAgentState):
    items = state.get("questions") or []
    if not items:
        return {"questions": items}
    llm = LLMService()
    question_list = [f"{i}. {item['question']}" for i, item in enumerate(items)]
    prompt = (
        "Provide suggested answers for each question.\n\n"
        + "\n".join(question_list)
        + "\n\nReturn JSON with a key 'answers' whose value is an array of objects with keys: "
        "index (integer matching the input order), suggested_answer."
    )
    try:
        payload = await llm.generate_json(prompt, system=ANSWERS_SYSTEM)
    except LLMError:
        logger.warning("Answer generation failed; leaving questions without answers")
        return {"questions": items}

    raw = payload.get("answers", [])
    if not isinstance(raw, list):
        return {"questions": items}

    by_index: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        answer = entry.get("suggested_answer")
        if isinstance(idx, int) and isinstance(answer, str) and answer:
            by_index[idx] = answer

    enriched: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if index in by_index:
            item = dict(item)
            item["suggested_answer"] = by_index[index]
        enriched.append(item)
    return {"questions": enriched}


workflow = StateGraph(InterviewAgentState)
workflow.add_node("analyze_jd", _analyze_jd)
workflow.add_node("generate_questions", _generate_questions)
workflow.add_node("generate_answers", _generate_answers)
workflow.set_entry_point("analyze_jd")
workflow.add_edge("analyze_jd", "generate_questions")
workflow.add_edge("generate_questions", "generate_answers")
workflow.add_edge("generate_answers", END)

interview_agent = workflow.compile()
