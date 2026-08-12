# Architecture

## Repository layout

```
copilot/
├── backend/               FastAPI + SQLAlchemy (async) + LangGraph
│   ├── app/
│   │   ├── api/           routers (auth, users, jobs, applications, resumes, cover_letters,
│   │   │                  interviews, analytics, notifications, automation, admin)
│   │   ├── agents/        LangGraph agents (job_match_agent)
│   │   ├── services/      business logic + external integrations
│   │   ├── repositories/  data-access layer
│   │   ├── schemas/       Pydantic request/response models
│   │   ├── db/models/     SQLAlchemy models
│   │   ├── core/          auth/deps/security helpers
│   │   ├── config.py      pydantic-settings env config
│   │   └── main.py        FastAPI app factory + router mounting
│   ├── alembic/           migrations (0001_initial_schema … 0008_add_application_management)
│   └── tests/             async pytest suite (~130 tests)
├── frontend/              React 18 + Vite + TS, React Router, TanStack Query, Zustand, Axios
│   └── src/
│       ├── pages/         Login, Signup, ForgotPassword, Dashboard, Resume, Jobs, Applications,
│       │                  ApplicationDetails, CoverLetters, InterviewPrep, Automation,
│       │                  Notifications, Admin, NotFound
│       ├── services/api.ts  single axios instance (auth interceptor + silent refresh)
│       ├── store/         authStore, themeStore
│       └── components/    shared UI
├── infra/                 deployment/container artifacts
└── docs/                  this documentation set
```

## Backend stack

- **FastAPI** with async endpoints; routers under `app/api/*.py` (flat package, no `api/v1`).
- **SQLAlchemy 2.0** async ORM (`AsyncSession`), models in `app/db/models`.
- **Alembic** for schema migrations (currently incomplete — see `DATABASE.md`).
- **LangGraph** state-graph agent for job matching (`app/agents/job_match_agent.py`).
- **httpx** for outbound fetches (job feeds, job-page analysis).
- **python-jose + passlib** for JWT and password hashing.
- External APIs: OpenAI-compatible LLM (Groq via `OPENAI_BASE_URL`), JSearch (RapidAPI), and the free
  Remotive / Jobicy / Arbeitnow feeds.

## Frontend stack

- React 18 + TypeScript, Vite build (`tsc -b && vite build`).
- React Router v6; `ProtectedRoute` + shared `Layout`; `/` redirects to `/dashboard`.
- TanStack Query for server state; Zustand for auth/theme; Axios with a single base URL
  (`http://localhost:8001`, override via `VITE_API_URL`) and a request interceptor that attaches the access
  token and transparently retries once after a `/auth/refresh`.
- One API service module (`services/api.ts`); no per-feature mock layer, no seeded demo rows.

## Application Management + CRM module

`app/services/application_service.py` owns all application lifecycle rules (thin router, fat service):

- **15 statuses** with validated transitions (`can_transition` in the model); terminal → reopen allowed and
  recorded; `UNKNOWN` → anything; same-status is a no-op.
- **Immutable snapshot** (`application_snapshots`) freezes job details at creation so the job row can change
  without corrupting the application record.
- **Frozen document versions** (`application_documents`) capture the resume/cover-letter used; downloads are
  HMAC-signed URLs with 24h expiry (secret in `settings.SECRET_KEY`).
- **Tracking** — status history, audit events, notes, tags, reminders (each transition/reminder can create a
  `Notification`).
- **Analytics/performance/export** — `get_analytics`, `get_performance` (n≥3 suppression), `export_csv`; all
  derived from real rows, drafts excluded.
- **Follow-up assistant** — recommends only after 7 days and drafts a message; never sends.
- **`delete_application`** removes all CRM rows (snapshot/history/notes/tags/reminders/audit/documents) before
  deleting the application (no FK cascades).
- Frontend: `/applications` dashboard (stats, needs-attention, search/filter/sort, CSV export) and
  `/applications/:id` details page (Overview / Timeline / Notes / Documents / Follow-up / Reminders tabs).

## Request flow

```
Browser ──(Bearer token, httpOnly refresh cookie)──▶ FastAPI router
                                                      │
                                                      ▼
                                              service layer
                                                      │
                              ┌───────────────────────┼─────────────────────┐
                              ▼                       ▼                     ▼
                         repositories          external APIs          LangGraph agents
                         (SQLAlchemy)          (LLM, JSearch,         (job_match_agent)
                                              Remotive/Jobicy)
```

## Auth flow

- Login returns an access token (Bearer, ~short-lived) and a refresh token stored in an httpOnly cookie.
- Frontend interceptor retries 401 responses once using the refresh endpoint; on failure it logs out and
  redirects to `/login`.
- Logout revokes the refresh token row.

## Conventions

- Backend: async-first, repository pattern, services own business rules, routers stay thin.
- Lint/type: `ruff check app`, `mypy app`; both must be clean before a phase ships.
- Frontend: feature-per-page under `src/pages`, shared UI in `src/components`, server data via TanStack Query.
- No comments are added to code unless requested.
