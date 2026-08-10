from app.db.models.application import Application, ApplicationStatus
from app.db.models.company import Company
from app.db.models.cover_letter import CoverLetter, CoverLetterStatus
from app.db.models.interview_question import InterviewQuestion, QuestionCategory
from app.db.models.job import Job, JobType
from app.db.models.notification import Notification, NotificationType
from app.db.models.resume import Resume


async def seed_job(
    db,
    title="Software Engineer",
    company_name="Acme Corp",
    country=None,
    source=None,
    source_url=None,
    canonical_url=None,
    source_job_id=None,
    location="Remote",
    job_type=JobType.REMOTE,
) -> int:
    company = Company(name=company_name)
    db.add(company)
    await db.flush()
    job = Job(
        company_id=company.id,
        title=title,
        description="Python backend role focused on building REST APIs.",
        location=location,
        country=country,
        job_type=job_type,
        source=source,
        source_url=source_url,
        canonical_url=canonical_url,
        source_job_id=source_job_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job.id


async def create_application(db, user_id: int, job_id: int, status: ApplicationStatus = ApplicationStatus.DRAFT) -> int:
    app = Application(user_id=user_id, job_id=job_id, status=status.value)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app.id


async def create_cover_letter(db, user_id: int, job_id: int, content: str = "Dear hiring manager") -> int:
    letter = CoverLetter(
        user_id=user_id,
        job_id=job_id,
        content=content,
        status=CoverLetterStatus.DRAFT,
    )
    db.add(letter)
    await db.commit()
    await db.refresh(letter)
    return letter.id


async def create_interview_question(
    db,
    user_id: int,
    job_id: int,
    category: QuestionCategory = QuestionCategory.BEHAVIORAL,
    question: str = "Tell me about yourself?",
) -> int:
    q = InterviewQuestion(user_id=user_id, job_id=job_id, category=category, question=question)
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q.id


async def create_resume(
    db,
    user_id: int,
    parsed_data: str = "Python backend developer with FastAPI, SQL, and AWS experience.",
) -> int:
    resume = Resume(
        user_id=user_id,
        title="My Resume",
        file_path="/tmp/resume.pdf",
        file_type="pdf",
        parsed_data=parsed_data,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume.id


async def create_notification(db, user_id: int, title: str = "Reminder", is_read: int = 0) -> int:
    notif = Notification(user_id=user_id, type=NotificationType.SYSTEM, title=title, is_read=is_read)
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif.id
