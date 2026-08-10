"""Job Intelligence Engine: deterministic market intelligence over the job corpus.

Everything here is computed from enriched jobs (skills_required CSV, seniority, salary,
country, job_type, posted_at). No per-request LLM calls so the endpoints stay fast and
production-safe; the personalized profile blends user resume skills with market demand.
"""

import json
import logging
from collections import Counter
from datetime import date, timedelta
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company import Company
from app.db.models.job import Job, JobType
from app.db.models.resume import Resume

logger = logging.getLogger(__name__)

# Soft/business skills that appear as boilerplate in most postings. Their raw counts are
# damped so they do not crowd out hard, actionable skills in demand rankings.
GENERIC_SKILLS = {
    "communication",
    "leadership",
    "strategy",
    "operations",
    "growth",
    "sales",
    "marketing",
    "finance",
    "accounting",
    "legal",
    "hr",
    "data protection",
    "presentation",
    "stakeholder management",
    "people management",
    "research",
}
GENERIC_SKILL_DAMP = 0.4


def _demand_count(skill: str, raw_count: int) -> int:
    if skill in GENERIC_SKILLS:
        return max(1, int(raw_count * GENERIC_SKILL_DAMP))
    return raw_count


def _split_skills(csv_value: str | None) -> list[str]:
    if not csv_value:
        return []
    return [s.strip() for s in csv_value.split(",") if s.strip()]


def _salary_midpoint(job: Job) -> int | None:
    if job.salary_min is not None and job.salary_max is not None:
        return (job.salary_min + job.salary_max) // 2
    if job.salary_min is not None:
        return job.salary_min
    if job.salary_max is not None:
        return job.salary_max
    return None


def _percentile(sorted_values: list[int], pct: float) -> int:
    if not sorted_values:
        return 0
    index = int(pct / 100 * (len(sorted_values) - 1) + 0.5)
    index = min(len(sorted_values) - 1, max(0, index))
    return sorted_values[index]


async def _load_jobs(db: AsyncSession, country: str | None = None) -> list[tuple[Job, str | None]]:
    stmt = select(Job, Company.name).join(Company)
    if country:
        stmt = stmt.where(Job.country.ilike(f"%{country}%"))
    rows = (await db.execute(stmt)).all()
    return [(job, name) for job, name in rows]


class JobIntelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def summary(self, country: str | None = None) -> dict:
        rows = await _load_jobs(self.db, country)
        jobs = [job for job, _ in rows]
        salaries = sorted(s for s in (_salary_midpoint(j) for j in jobs) if s is not None)
        remote_count = sum(1 for j in jobs if j.job_type == JobType.REMOTE)
        since = date.today() - timedelta(days=30)
        recent = sum(1 for j in jobs if j.posted_at and j.posted_at.date() >= since)

        skills: Counter[str] = Counter()
        for job in jobs:
            skills.update(_split_skills(job.skills_required))

        total = len(jobs)
        return {
            "total_jobs": total,
            "distinct_companies": len({name for _, name in rows if name}),
            "median_salary": int(median(salaries)) if salaries else None,
            "avg_salary": round(sum(salaries) / len(salaries)) if salaries else None,
            "remote_share_pct": round(remote_count / total * 100) if total else 0,
            "jobs_posted_30d": recent,
            "demand_index": round(recent / total * 100) if total else 0,
            "top_skills": [
                {"skill": skill, "count": _demand_count(skill, count)}
                for skill, count in skills.most_common(5)
            ],
        }

    async def top_skills(self, limit: int = 20, query: str = "", country: str | None = None) -> list[dict]:
        rows = await _load_jobs(self.db, country)
        skills: Counter[str] = Counter()
        for job, _ in rows:
            skills.update(_split_skills(job.skills_required))
        q = query.strip().lower()
        items: list[dict[str, Any]] = [
            {"skill": s, "count": _demand_count(s, c)}
            for s, c in skills.most_common(limit * 3)
            if not q or q in s.lower()
        ]
        items.sort(key=lambda item: item["count"], reverse=True)
        return items[:limit]

    async def top_companies(self, limit: int = 10, country: str | None = None) -> list[dict]:
        rows = await _load_jobs(self.db, country)
        by_company: dict[str, list[Job]] = {}
        for job, company_name in rows:
            if not company_name:
                continue
            by_company.setdefault(company_name, []).append(job)
        result: list[dict[str, Any]] = []
        for company, jobs in by_company.items():
            salaries = sorted(s for s in (_salary_midpoint(j) for j in jobs) if s is not None)
            result.append(
                {
                    "company": company,
                    "job_count": len(jobs),
                    "avg_salary": round(sum(salaries) / len(salaries)) if salaries else None,
                }
            )
        result.sort(key=lambda item: item["job_count"], reverse=True)
        return result[:limit]

    async def salary_benchmarks(self, query: str = "", country: str | None = None) -> list[dict]:
        rows = await _load_jobs(self.db, country)
        by_seniority: dict[str, list[int]] = {}
        for job, _ in rows:
            if not job.seniority:
                continue
            if query and query.lower() not in (job.title or "").lower():
                continue
            midpoint = _salary_midpoint(job)
            if midpoint is not None:
                by_seniority.setdefault(job.seniority, []).append(midpoint)
        result: list[dict[str, Any]] = []
        for seniority, salaries in by_seniority.items():
            sorted_salaries = sorted(salaries)
            result.append(
                {
                    "seniority": seniority,
                    "count": len(salaries),
                    "avg_salary": round(sum(salaries) / len(salaries)),
                    "median_salary": int(median(sorted_salaries)),
                    "p25": _percentile(sorted_salaries, 25),
                    "p75": _percentile(sorted_salaries, 75),
                }
            )
        order = ["Intern", "Junior", "Associate", "Mid-level", "Senior", "Lead", "Staff", "Principal", "Manager", "Head", "Director", "VP", "Executive"]
        result.sort(key=lambda item: order.index(item["seniority"]) if item["seniority"] in order else len(order))
        return result

    async def trends(self, days: int = 30, country: str | None = None) -> list[dict]:
        stmt = (
            select(func.date(Job.posted_at), func.count(Job.id))
            .where(Job.posted_at.isnot(None))
            .group_by(func.date(Job.posted_at))
        )
        if country:
            stmt = stmt.where(Job.country.ilike(f"%{country}%"))
        result = await self.db.execute(stmt)
        counts = {str(row[0]): row[1] for row in result.all()}
        start = date.today() - timedelta(days=days - 1)
        return [
            {"date": (start + timedelta(days=i)).isoformat(), "count": counts.get((start + timedelta(days=i)).isoformat(), 0)}
            for i in range(days)
        ]

    async def profile(self, user_id: int) -> dict:
        resume_result = await self.db.execute(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
        )
        resume = resume_result.scalar_one_or_none()
        user_skills: list[str] = []
        if resume and resume.parsed_data:
            try:
                parsed = json.loads(resume.parsed_data)
                if isinstance(parsed, dict) and isinstance(parsed.get("skills"), list):
                    user_skills = [str(s).strip().lower() for s in parsed["skills"] if str(s).strip()]
            except (TypeError, ValueError):
                pass

        rows = await _load_jobs(self.db)
        market: Counter[str] = Counter()
        for job, _ in rows:
            market.update(_split_skills(job.skills_required))

        matched_jobs = [job for job, _ in rows if _job_has_any_skill(job, user_skills)]
        salary_band = sorted(s for s in (_salary_midpoint(j) for j in matched_jobs) if s is not None)
        coverage = round(len([s for s in user_skills if s in market]) / len(user_skills) * 100) if user_skills else 0

        user_skill_intel = []
        for skill in user_skills:
            count = sum(1 for listed in market if _skill_matches(listed, skill))
            if count:
                user_skill_intel.append({"skill": skill, "jobs_count": count, "in_market": True})

        top_market = [s for s, _ in market.most_common() if not any(_skill_matches(s, us) for us in user_skills)]
        recommended: list[dict[str, Any]] = [
            {"skill": s, "count": _demand_count(s, market[s])}
            for s in top_market[:20]
        ]
        recommended.sort(key=lambda item: item["count"], reverse=True)
        recommended = recommended[:8]

        return {
            "has_resume": bool(resume),
            "user_skills": user_skill_intel[:25],
            "recommended_skills": recommended,
            "coverage_score": coverage,
            "median_target_salary": int(median(salary_band)) if salary_band else None,
            "target_jobs_count": len(matched_jobs),
            "total_jobs": len(rows),
        }


def _skill_matches(listed_skill: str, user_skill: str) -> bool:
    listed = listed_skill.lower()
    user = user_skill.lower()
    if user in listed or listed in user:
        return True
    if user == "js" and "javascript" in listed:
        return True
    return bool(user == "javascript" and listed == "js")


def _job_has_any_skill(job: Job, user_skills: list[str]) -> bool:
    if not user_skills:
        return False
    return any(
        any(_skill_matches(listed, us) for us in user_skills)
        for listed in _split_skills(job.skills_required)
    )
