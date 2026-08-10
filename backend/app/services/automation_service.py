import contextlib
import ipaddress
import json
import logging
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.automation_session import AutomationSession, AutomationStatus
from app.db.models.resume import Resume
from app.db.models.user import User
from app.repositories.automation_session_repo import AutomationSessionRepository
from app.repositories.job_repo import JobRepository
from app.services.llm_service import LLMError, LLMService

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

MAX_REDIRECTS = 5

_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal"}


def _is_private_host(host: str) -> bool:
    normalized = host.rstrip(".").lower()
    if normalized in _BLOCKED_HOSTS or normalized.endswith(".local"):
        return True
    try:
        infos = socket.getaddrinfo(normalized, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return True
    return False


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https job page URLs are supported")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL has no hostname")
    if _is_private_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Private or internal URLs are not allowed")


class _FormFieldParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields: list[dict] = []
        self.text: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self._in_script = True
        if tag in ("input", "select", "textarea") and not attr_map.get("hidden"):
            name = attr_map.get("name") or attr_map.get("id") or ""
            if name:
                self.fields.append(
                    {
                        "name": name,
                        "type": attr_map.get("type", tag if tag != "textarea" else "textarea"),
                        "label": attr_map.get("placeholder") or attr_map.get("aria-label") or name,
                    }
                )

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._in_script = False

    def handle_data(self, data):
        if not self._in_script:
            stripped = " ".join(data.split())
            if stripped:
                self.text.append(stripped)


class AutomationService:
    def __init__(self, db: AsyncSession):
        self.session_repo = AutomationSessionRepository(db)
        self.job_repo = JobRepository(db)
        self.db = db
        self.llm = LLMService()

    async def start_session(self, user_id: int, job_id: int, job_url: str) -> AutomationSession:
        job = await self.job_repo.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        session = await self.session_repo.create(
            {
                "user_id": user_id,
                "job_id": job_id,
                "job_url": job_url,
                "status": AutomationStatus.STARTED,
                "steps": json.dumps([{"step": "created", "status": "done", "detail": "Session created"}]),
                "confirmation_required": True,
            }
        )
        return session

    async def analyze_page(self, session_id: int) -> AutomationSession:
        session = await self._get_own_session(session_id)
        if session.status in (AutomationStatus.COMPLETED, AutomationStatus.CANCELLED, AutomationStatus.FAILED):
            raise HTTPException(status_code=400, detail="Session is already finished")
        if not session.job_url:
            raise HTTPException(status_code=400, detail="Session has no target URL")

        steps = [
            {"step": "fetch_page", "status": "running", "detail": f"Fetching {session.job_url}"},
        ]
        page_text, fields = await self._fetch_page(session.job_url)
        steps[0]["status"] = "done"
        steps[0]["detail"] = f"Fetched page ({len(page_text)} chars, {len(fields)} form fields found)"

        profile = await self._build_profile(session.user_id)
        prompt = (
            "You are a job-application assistant. Based on the job page content and the candidate profile, "
            "generate a JSON object to pre-fill the application form.\n"
            "Return ONLY valid JSON with keys:\n"
            '- "summary": short summary of the job/company (2-3 sentences)\n'
            '- "filled": array of { "name": field_name, "value": value_to_fill } for each field you can fill '
            "from the candidate profile (full name, email, phone, location, headline, summary, resume text, skills)\n"
            '- "notes": array of strings with anything the user must fill manually\n\n'
            f"Candidate profile:\n{json.dumps(profile, indent=2)}\n\n"
            f"Job page text (truncated):\n{page_text[:8000]}\n\n"
            f"Form fields detected:\n{json.dumps(fields, indent=2)}"
        )
        steps.append({"step": "ai_fill", "status": "running", "detail": "Analyzing page with AI"})
        try:
            payload = await self.llm.generate_json(prompt)
            steps[-1]["status"] = "done"
            steps[-1]["detail"] = "Form fields analyzed and draft prepared"
            result = {
                "url": session.job_url,
                "summary": payload.get("summary", ""),
                "filled": payload.get("filled", []),
                "notes": payload.get("notes", []),
            }
        except LLMError as exc:
            logger.error("Automation AI fill failed: %s", exc)
            steps[-1]["status"] = "failed"
            steps[-1]["detail"] = "AI fill failed"
            result = {
                "url": session.job_url,
                "summary": "AI service could not analyze the page.",
                "filled": [],
                "notes": ["AI service unavailable."],
            }

        session.steps = json.dumps(steps, ensure_ascii=False)
        session.result = json.dumps(result, ensure_ascii=False, indent=2)
        session.status = AutomationStatus.RUNNING
        await self.session_repo.db.commit()
        await self.session_repo.db.refresh(session)
        return session

    async def _fetch_page(self, url: str) -> tuple[str, list[dict]]:
        _validate_public_url(url)
        current = url
        try:
            async with httpx.AsyncClient(
                timeout=20, follow_redirects=False, headers={"User-Agent": USER_AGENT}
            ) as client:
                resp = await client.get(current)
                redirects = 0
                while resp.is_redirect and redirects < MAX_REDIRECTS:
                    redirects += 1
                    location = resp.headers.get("location")
                    if not location:
                        break
                    current = str(httpx.URL(current).join(location))
                    _validate_public_url(current)
                    resp = await client.get(current)
                resp.raise_for_status()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not fetch job page: {exc}") from exc

        content_type = resp.headers.get("content-type", "")
        parser = _FormFieldParser()
        if "html" in content_type.lower() or b"<" in resp.content[:1024]:
            with contextlib.suppress(Exception):
                parser.feed(resp.text)
        else:
            raise HTTPException(status_code=502, detail="Target URL is not an HTML application page.")

        text = " ".join(parser.text)
        if not text:
            text = " ".join(resp.text.split())[:8000]
        return text[:8000], parser.fields

    async def _build_profile(self, user_id: int) -> dict:
        user = await self.db.execute(select(User).where(User.id == user_id))
        u = user.scalar_one_or_none()
        profile_data: dict = {}
        if u:
            profile_data["name"] = u.full_name
            profile_data["email"] = u.email
        from app.db.models.profile import Profile

        profile = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        p = profile.scalar_one_or_none()
        if p:
            profile_data.update(
                {
                    "headline": p.headline,
                    "phone": p.phone,
                    "location": p.location,
                    "summary": p.summary,
                }
            )
        resume = await self.db.execute(select(Resume).where(Resume.user_id == user_id).order_by(Resume.id.desc()))
        r = resume.scalars().first()
        if r:
            profile_data["resume"] = r.parsed_data
        return profile_data

    async def _get_own_session(self, session_id: int) -> AutomationSession:
        session = await self.session_repo.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
