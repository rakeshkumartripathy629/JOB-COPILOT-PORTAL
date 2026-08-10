import json
import logging
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job
from app.db.models.resume import Resume
from app.services.llm_service import LLMError, LLMService

LLM_CANDIDATE_LIMIT = 20
RESULT_LIMIT = 20

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "you",
    "your",
    "our",
    "will",
    "have",
    "has",
    "are",
    "was",
    "were",
    "work",
    "working",
    "experience",
    "skills",
    "able",
    "ability",
    "using",
    "strong",
    "including",
    "such",
    "like",
    "role",
    "team",
    "client",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9+#.\-]{1,}", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _heuristic_score(job: Any, resume_text: str) -> int:
    job_text = " ".join(
        filter(
            None,
            [job.title, job.description or "", job.requirements or "", job.skills_required or ""],
        )
    )
    job_tokens = _tokens(job_text)
    resume_tokens = _tokens(resume_text)
    if not job_tokens:
        return 50
    overlap = job_tokens & resume_tokens
    if not overlap:
        return 10
    ratio = len(overlap) / len(job_tokens)
    return max(10, min(100, round(ratio * 100)))


def _heuristic_matched_skills(job: Any, resume_skills: list[str]) -> list[str]:
    """Fallback matched-skills computation when the LLM does not provide them."""
    job_text = " ".join(
        filter(
            None,
            [job.title, job.description or "", job.requirements or "", job.skills_required or ""],
        )
    ).lower()
    matched = [skill for skill in resume_skills if skill and skill.lower() in job_text]
    return matched[:20]


class JobMatchAgentState(TypedDict):
    db: AsyncSession
    user_id: int
    resume_id: int | None
    jobs: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    resume_skills: list[str]


async def _load_context(state: JobMatchAgentState):
    db = state["db"]
    resume = None
    if state.get("resume_id"):
        result = await db.execute(select(Resume).where(Resume.id == state["resume_id"]))
        resume = result.scalar_one_or_none()
    if not resume:
        resume_result = await db.execute(
            select(Resume).where(Resume.user_id == state["user_id"]).order_by(Resume.created_at.desc()).limit(1)
        )
        resume = resume_result.scalar_one_or_none()
    if not resume:
        return {"matches": []}

    job_result = await db.execute(select(Job, Company).join(Company).order_by(Job.created_at.desc()).limit(50))
    jobs = job_result.all()

    resume_skills: list[str] = []
    if resume.parsed_data:
        try:
            parsed = json.loads(resume.parsed_data)
            if isinstance(parsed, dict) and isinstance(parsed.get("skills"), list):
                resume_skills = [str(s).strip() for s in parsed["skills"] if str(s).strip()]
        except (TypeError, ValueError):
            pass

    resume_text = " ".join(filter(None, [resume.title, resume.parsed_data or ""]))
    return {
        "resume_skills": resume_skills,
        "jobs": [
            {
                "job": job,
                "company_name": company.name if company else None,
                "resume_text": resume_text,
            }
            for job, company in jobs
        ],
    }


async def _llm_scores(shortlist: list[dict[str, Any]], resume_text: str) -> dict[str, dict[str, Any]]:
    if not shortlist:
        return {}
    jobs_text = "\n".join(
        f"{job.id}. {job.title} | {job.location or 'Remote'} | "
        f"{job.job_type.value if job.job_type else ''} | "
        f"{(job.requirements or job.description or '')[:300]}"
        for entry in shortlist
        for job in [entry["job"]]
    )
    prompt = (
        "Score how well each job below matches this candidate. Use 0-100 integers; be strict "
        "(80+ only when most required skills are present in the resume, below 40 when "
        "the core skills are missing). Also list the candidate skills that appear in each job "
        "as matched_skills. Return ONLY JSON: "
        '{"matches": [{"id": <job id>, "match_score": <0-100 int>, "reason": "<one short sentence>", '
        '"matched_skills": ["<skill>", ...]}]}.\n\n'
        f"JOBS:\n{jobs_text}"
    )
    try:
        payload = await LLMService().generate_json(prompt, system=resume_text[:6000])
    except LLMError:
        logger.warning("LLM job scoring failed; falling back to heuristic scores")
        return {}
    result: dict[str, dict[str, Any]] = {}
    items = payload.get("matches")
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        score = item.get("match_score")
        if not isinstance(score, int | float) or not 0 <= score <= 100:
            continue
        matched = item.get("matched_skills")
        result[str(item["id"])] = {
            "match_score": round(score),
            "reason": (item.get("reason") or "").strip()[:200],
            "matched_skills": [str(s) for s in matched] if isinstance(matched, list) else None,
        }
    return result


async def _score_matches(state: JobMatchAgentState):
    candidates = state.get("jobs") or []
    if not candidates:
        return {"matches": []}

    resume_text = candidates[0]["resume_text"]
    resume_skills = state.get("resume_skills") or []
    ranked = sorted(
        candidates,
        key=lambda entry: _heuristic_score(entry["job"], resume_text),
        reverse=True,
    )
    shortlist = ranked[:LLM_CANDIDATE_LIMIT]
    llm_scores = await _llm_scores(shortlist, resume_text)

    scored: list[dict[str, Any]] = []
    for entry in shortlist:
        job = entry["job"]
        info = llm_scores.get(str(job.id), {})
        score = info.get("match_score") if isinstance(info.get("match_score"), int) else None
        if score is None:
            score = _heuristic_score(job, resume_text)
        matched = info.get("matched_skills")
        if not isinstance(matched, list):
            matched = _heuristic_matched_skills(job, resume_skills)
        scored.append(
            {
                "id": job.id,
                "title": job.title,
                "description": job.description,
                "location": job.location,
                "country": job.country,
                "job_type": job.job_type.value if job.job_type else None,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "seniority": job.seniority,
                "experience_min": job.experience_min,
                "experience_max": job.experience_max,
                "skills_required": job.skills_required,
                "source": job.source,
                "source_url": job.source_url,
                "created_at": job.created_at,
                "company_name": entry["company_name"],
                "match_score": score,
                "match_reason": info.get("reason"),
                "matched_skills": matched,
            }
        )
    scored.sort(key=lambda item: item["match_score"], reverse=True)
    return {"matches": scored[:RESULT_LIMIT]}


workflow = StateGraph(JobMatchAgentState)
workflow.add_node("load_context", _load_context)
workflow.add_node("score_matches", _score_matches)
workflow.set_entry_point("load_context")
workflow.add_edge("load_context", "score_matches")
workflow.add_edge("score_matches", END)

job_match_agent = workflow.compile()
