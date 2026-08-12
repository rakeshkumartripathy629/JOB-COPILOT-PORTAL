import contextlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.job import JobDetail, JobResponse, JobSearch
from app.schemas.job_search import (
    JobSearchResultCard,
    SearchHistoryItem,
    SearchProfileResponse,
    SearchResultsResponse,
    SearchSessionStatusResponse,
    SearchStartRequest,
    SearchStartResponse,
    SourceAvailabilityItem,
    SourcesStatusResponse,
)
from app.services.job_search_service import JobSearchService

router = APIRouter()


@router.get("/profile", response_model=SearchProfileResponse)
async def get_resume_search_profile(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import get_search_profile_for_user

    profile = await get_search_profile_for_user(db, current_user.id)
    if profile is None:
        return SearchProfileResponse(has_resume=False, profile=None)
    return SearchProfileResponse(has_resume=True, profile=profile.to_dict())


@router.post("/search", response_model=SearchStartResponse)
async def start_resume_driven_search(
    body: SearchStartRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import NoResumeError, run_search_task, start_search

    try:
        search_id = await start_search(
            db,
            user_id=current_user.id,
            time_range=body.time_range,
            remote=body.remote,
            sources=body.sources,
        )
    except NoResumeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(run_search_task, search_id)
    return SearchStartResponse(search_id=search_id)


@router.get("/search/{search_id}/status", response_model=SearchSessionStatusResponse)
async def get_search_status(
    search_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import get_session_with_status

    data = await get_session_with_status(db, current_user.id, search_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    return SearchSessionStatusResponse(**data)


@router.get("/search/{search_id}", response_model=SearchResultsResponse)
async def get_search_results(
    search_id: int,
    time_range: str = "any",
    match_min: int = 0,
    source: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import get_search_results, get_session_with_status

    session = await get_session_with_status(db, current_user.id, search_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Search session not found")
    jobs = await get_search_results(
        db,
        current_user.id,
        search_id,
        time_range=time_range,
        match_min=match_min,
        source=source,
    )
    message = None
    if session["status"] == "COMPLETED" and not jobs:
        message = "No jobs match your current filters."
    elif session["status"] == "FAILED":
        message = session["error"] or "Search failed."
    return SearchResultsResponse(
        search_id=search_id,
        status=session["status"],
        message=message,
        jobs=[JobSearchResultCard(**job) for job in jobs],
    )


@router.get("/searches", response_model=list[SearchHistoryItem])
async def get_search_history(
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import user_search_history

    return await user_search_history(db, current_user.id, limit)


@router.delete("/search/{search_id}")
async def delete_search(
    search_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import delete_search_session

    deleted = await delete_search_session(db, current_user.id, search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Search session not found")
    return {"deleted": True}


@router.get("/search", response_model=list[JobResponse])
async def search_jobs(
    query: str = "",
    location: str = "",
    country: str = "",
    remote_only: bool = False,
    salary_min: int = 0,
    experience_level: str = "",
    page: int = 1,
    limit: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = JobSearchService(db)
    params = JobSearch(
        query=query,
        location=location,
        country=country,
        remote_only=remote_only,
        salary_min=salary_min,
        experience_level=experience_level,
        page=page,
        limit=limit,
    )
    return await service.search(params)


@router.get("/suggestions", response_model=list[JobResponse])
async def get_suggestions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.agents.job_match_agent import job_match_agent

    result = await job_match_agent.ainvoke(
        {
            "db": db,
            "user_id": current_user.id,
            "resume_id": None,
            "jobs": [],
            "matches": [],
            "resume_skills": [],
        }
    )
    return result.get("matches", [])


@router.get("/sources/status", response_model=SourcesStatusResponse)
async def get_job_sources_status(
    current_user=Depends(get_current_user),
):
    from app.services.live_search_service import get_sources_status

    return SourcesStatusResponse(
        sources=[SourceAvailabilityItem(**item) for item in get_sources_status()]
    )


@router.post("/search/{search_id}/refresh", response_model=SearchStartResponse)
async def refresh_search(
    search_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_search_service import refresh_search_session, run_search_task

    if not await refresh_search_session(db, current_user.id, search_id):
        raise HTTPException(status_code=404, detail="Search session not found")
    background_tasks.add_task(run_search_task, search_id)
    return SearchStartResponse(search_id=search_id, status="SEARCHING")


@router.post("/refresh")
async def refresh_jobs(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.live_jobs_service import refresh_jobs as live_refresh

    return await live_refresh(db)


@router.post("/refresh-india")
async def refresh_india_jobs(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.resume_job_service import fetch_jobs_for_latest_resume

    return await fetch_jobs_for_latest_resume(db, current_user.id)


@router.get("/intel/summary")
async def job_intel_summary(
    country: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.job_intel_service import JobIntelService

    return await JobIntelService(db).summary(country or None)


@router.get("/intel/skills")
async def job_intel_skills(
    limit: int = 20,
    query: str = "",
    country: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.job_intel_service import JobIntelService

    return await JobIntelService(db).top_skills(limit=min(limit, 50), query=query, country=country or None)


@router.get("/intel/companies")
async def job_intel_companies(
    limit: int = 10,
    country: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.job_intel_service import JobIntelService

    return await JobIntelService(db).top_companies(limit=min(limit, 50), country=country or None)


@router.get("/intel/salary")
async def job_intel_salary(
    query: str = "",
    country: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.job_intel_service import JobIntelService

    return await JobIntelService(db).salary_benchmarks(query=query, country=country or None)


@router.get("/intel/trends")
async def job_intel_trends(
    days: int = 30,
    country: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.job_intel_service import JobIntelService

    return await JobIntelService(db).trends(days=min(max(days, 7), 90), country=country or None)


@router.get("/intel/profile")
async def job_intel_profile(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.job_intel_service import JobIntelService

    return await JobIntelService(db).profile(current_user.id)


@router.post("/enrich")
async def enrich_all_jobs(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run the enrichment pipeline over all jobs (idempotent)."""
    from sqlalchemy import select

    from app.db.models.company import Company
    from app.db.models.job import Job
    from app.services.job_enrichment_service import enrich

    rows = (await db.execute(select(Job, Company.name).join(Company))).all()
    updated = 0
    for job, company_name in rows:
        fields = enrich(job.title, job.description, job.requirements, company_name, job.location)
        if (
            job.seniority != fields["seniority"]
            or job.experience_min != fields["experience_min"]
            or job.experience_max != fields["experience_max"]
            or job.skills_required != fields["skills_required"]
            or job.dedupe_key != fields["dedupe_key"]
            or job.country != fields["country"]
        ):
            job.seniority = fields["seniority"]
            job.experience_min = fields["experience_min"]
            job.experience_max = fields["experience_max"]
            job.skills_required = fields["skills_required"]
            job.dedupe_key = fields["dedupe_key"]
            job.country = fields["country"] or job.country
            job.salary_currency = job.salary_currency or "USD"
            updated += 1
    await db.commit()
    return {"updated": updated, "total": len(rows)}


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.job_repo import JobRepository

    repo = JobRepository(db)
    result = await repo.get_by_id(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    job, company = result
    return JobDetail(
        id=job.id,
        title=job.title,
        company_name=company.name if company else None,
        location=job.location,
        country=job.country,
        job_type=job.job_type.value if job.job_type else None,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        experience_level=job.experience_level,
        seniority=job.seniority,
        experience_min=job.experience_min,
        experience_max=job.experience_max,
        skills_required=job.skills_required,
        description=job.description,
        requirements=job.requirements,
        source=job.source,
        source_url=job.source_url,
        posted_at=job.posted_at,
        created_at=job.created_at,
    )


@router.post("/{job_id}/save")
async def save_job(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models.application import ApplicationSource, ApplicationStatus
    from app.repositories.application_repo import ApplicationRepository
    from app.services import application_service

    repo = ApplicationRepository(db)
    existing = await repo.get_by_user_and_job(current_user.id, job_id)
    if existing:
        existing.status = ApplicationStatus.DRAFT.value
        await db.commit()
    else:
        with contextlib.suppress(application_service.DuplicateApplicationError):
            await application_service.create_application(
                db,
                user_id=current_user.id,
                job_id=job_id,
                application_source=ApplicationSource.SAVED_JOB.value,
                status=ApplicationStatus.DRAFT.value,
            )
    return {"detail": "Job saved"}

@router.delete("/{job_id}/save")
async def unsave_job(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.application_repo import ApplicationRepository
    from app.services import application_service

    repo = ApplicationRepository(db)
    existing = await repo.get_by_user_and_job(current_user.id, job_id)
    if existing:
        with contextlib.suppress(application_service.ApplicationNotFoundError):
            await application_service.delete_application(db, current_user.id, existing.id)
    return {"detail": "Job unsaved"}


async def _get_job_or_404(db: AsyncSession, job_id: int):
    from sqlalchemy import select

    from app.db.models.job import Job

    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _match_context(db: AsyncSession, user_id: int):
    from app.db.models.user import User
    from app.services.career_evidence_service import ensure_career_vault, get_resume_facts
    from app.services.search_profile_service import build_search_profile

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return None, [], None
    profile = await build_search_profile(db, user)
    if profile is None:
        return None, [], user
    await ensure_career_vault(db, user_id)
    facts = await get_resume_facts(db, user_id)
    return profile, facts, user


def _gate_no_profile(profile) -> None:
    if profile is None:
        raise HTTPException(status_code=400, detail="Upload your resume to compute a personalized match.")


@router.get("/{job_id}/match")
async def job_advanced_match(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.career import AdvancedMatchOut
    from app.services.advanced_match_service import compute_advanced_match

    job = await _get_job_or_404(db, job_id)
    profile, facts, _user = await _match_context(db, current_user.id)
    _gate_no_profile(profile)
    match = await compute_advanced_match(db, user_id=current_user.id, job=job, profile=profile, facts=facts)
    return AdvancedMatchOut(**match.to_dict())


@router.get("/{job_id}/evidence")
async def job_evidence(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.career import JobEvidenceOut
    from app.services.advanced_match_service import compute_and_persist, get_persisted_evidence

    job = await _get_job_or_404(db, job_id)
    rows = await get_persisted_evidence(db, current_user.id, job_id)
    if not rows:
        profile, facts, _user = await _match_context(db, current_user.id)
        _gate_no_profile(profile)
        await compute_and_persist(db, user_id=current_user.id, job=job, profile=profile, facts=facts)
        rows = await get_persisted_evidence(db, current_user.id, job_id)
    return [
        JobEvidenceOut(
            id=r.id,
            career_fact_id=r.career_fact_id,
            fact_name=r.fact_name,
            fact_type=r.fact_type,
            classification=r.classification,
            reason=r.reason,
            evidence_text=r.evidence_text,
            confidence=r.confidence,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{job_id}/requirement-matrix")
async def job_requirement_matrix(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.career import RequirementMatrixItem
    from app.services.advanced_match_service import compute_advanced_match

    job = await _get_job_or_404(db, job_id)
    profile, facts, _user = await _match_context(db, current_user.id)
    _gate_no_profile(profile)
    match = await compute_advanced_match(db, user_id=current_user.id, job=job, profile=profile, facts=facts)
    return [RequirementMatrixItem(**item) for item in match.requirements]


@router.get("/{job_id}/should-apply")
async def job_should_apply(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.advanced_match_service import compute_advanced_match
    from app.services.should_apply_service import decide_should_apply

    job = await _get_job_or_404(db, job_id)
    profile, facts, _user = await _match_context(db, current_user.id)
    _gate_no_profile(profile)
    match = await compute_advanced_match(db, user_id=current_user.id, job=job, profile=profile, facts=facts)
    return decide_should_apply(match).to_dict()


@router.get("/{job_id}/roi")
async def job_roi(
    job_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.advanced_match_service import compute_advanced_match
    from app.services.application_roi_service import compute_application_roi
    from app.services.job_freshness_service import classify_freshness
    from app.services.should_apply_service import decide_should_apply

    job = await _get_job_or_404(db, job_id)
    profile, facts, _user = await _match_context(db, current_user.id)
    _gate_no_profile(profile)
    match = await compute_advanced_match(db, user_id=current_user.id, job=job, profile=profile, facts=facts)
    should_apply = decide_should_apply(match)
    freshness, _posting_verified = classify_freshness(job.posted_at, job.updated_at, job.discovered_at)
    return compute_application_roi(
        match,
        should_apply,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        job_quality_score=job.job_quality_score,
        freshness=freshness.value,
    )
