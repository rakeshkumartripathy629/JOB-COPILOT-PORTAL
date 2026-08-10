import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job
from app.db.models.resume import Resume
from app.services.llm_service import LLMError, LLMService

logger = logging.getLogger(__name__)

DRAFT_SYSTEM = (
    "You are an expert career coach writing tailored, professional cover letters. "
    "Match the tone of the company and job description. Keep it under 400 words."
)

REFINE_SYSTEM = (
    "You are a meticulous editor. Polish the draft cover letter for tone, grammar, "
    "and impact. Keep it under 400 words. Return only the final letter text."
)


class CoverLetterAgentState(TypedDict):
    db: AsyncSession
    user_id: int
    job_id: int
    resume_id: int | None
    context: dict[str, Any]
    draft: str
    final: str


async def _gather_context(state: CoverLetterAgentState):
    db = state["db"]
    result = await db.execute(select(Job, Company).join(Company).where(Job.id == state["job_id"]))
    row = result.first()
    if not row:
        return {"context": {}, "final": ""}
    job, company = row

    resume = None
    if state.get("resume_id"):
        resume_result = await db.execute(select(Resume).where(Resume.id == state["resume_id"]))
        resume = resume_result.scalar_one_or_none()

    context = {
        "job_title": job.title,
        "company_name": company.name if company else "Unknown",
        "location": job.location or "Not specified",
        "description": job.description or "Not provided",
        "requirements": job.requirements or "Not provided",
        "resume_data": resume.parsed_data if resume and resume.parsed_data else "Not provided",
    }
    return {"context": context}


async def _generate_draft(state: CoverLetterAgentState):
    ctx = state.get("context") or {}
    if not ctx.get("job_title"):
        return {"draft": ""}
    prompt = (
        "Write a professional cover letter for the following job.\n\n"
        f"Job title: {ctx['job_title']}\n"
        f"Company: {ctx['company_name']}\n"
        f"Location: {ctx['location']}\n"
        f"Job description: {ctx['description']}\n"
        f"Requirements: {ctx['requirements']}\n\n"
        f"Resume data:\n{ctx['resume_data']}\n\n"
        "Address the key requirements in the job description, highlight relevant experience "
        "from the resume, and close with a call to action."
    )
    llm = LLMService()
    try:
        draft = await llm.generate(prompt, system=DRAFT_SYSTEM)
    except LLMError:
        logger.error("Cover letter draft generation failed")
        raise
    return {"draft": draft}


async def _refine(state: CoverLetterAgentState):
    draft = state.get("draft") or ""
    if not draft:
        return {"final": ""}
    llm = LLMService()
    try:
        final = await llm.generate(f"Draft:\n{draft}", system=REFINE_SYSTEM)
    except LLMError:
        logger.error("Cover letter refinement failed")
        raise
    return {"final": final}


workflow = StateGraph(CoverLetterAgentState)
workflow.add_node("gather_context", _gather_context)
workflow.add_node("generate_draft", _generate_draft)
workflow.add_node("refine", _refine)
workflow.set_entry_point("gather_context")
workflow.add_edge("gather_context", "generate_draft")
workflow.add_edge("generate_draft", "refine")
workflow.add_edge("refine", END)

cover_letter_agent = workflow.compile()
