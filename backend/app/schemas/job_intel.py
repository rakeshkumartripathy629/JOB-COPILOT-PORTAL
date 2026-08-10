from pydantic import BaseModel


class SkillDemand(BaseModel):
    skill: str
    count: int


class CompanyIntel(BaseModel):
    company: str
    job_count: int
    avg_salary: int | None = None


class SalaryBenchmark(BaseModel):
    seniority: str
    count: int
    avg_salary: int | None = None
    median_salary: int | None = None
    p25: int | None = None
    p75: int | None = None


class TrendPoint(BaseModel):
    date: str
    count: int


class JobIntelSummary(BaseModel):
    total_jobs: int
    distinct_companies: int
    median_salary: int | None = None
    avg_salary: int | None = None
    remote_share_pct: int
    jobs_posted_30d: int
    demand_index: int
    top_skills: list[SkillDemand]


class UserSkillIntel(BaseModel):
    skill: str
    jobs_count: int
    in_market: bool


class CareerIntel(BaseModel):
    has_resume: bool
    user_skills: list[UserSkillIntel]
    recommended_skills: list[SkillDemand]
    coverage_score: int
    median_target_salary: int | None = None
    target_jobs_count: int
    total_jobs: int
