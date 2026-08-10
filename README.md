# AI Job Copilot

AI-powered job application assistant. Tracks job applications, parses resumes with ATS scoring, generates cover letters and interview questions, and surfaces analytics and notifications.

## Stack

| Layer    | Tech |
| -------- | ---- |
| Backend  | FastAPI, SQLAlchemy 2 (async), Alembic, LangGraph agents, Celery + Redis |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, TanStack Query, Zustand |
| Storage  | SQLite (dev) / PostgreSQL (prod), ChromaDB |
| CI       | GitHub Actions (ruff, mypy, pytest, frontend lint + build) |

## Repository layout

```
backend/   FastAPI app: app/api, app/agents, app/services, app/repositories,
           app/db/models, app/tasks, app/schemas, alembic/, tests/
frontend/  React + Vite SPA
.github/   CI workflow (ci.yml) and deploy placeholder
docker-compose.yml   (deployment; used at deploy time)
```

## Prerequisites

- Python 3.12+ (tested on 3.12 and 3.14)
- Node.js 20+
- (Optional) Redis for Celery background tasks

## Backend setup

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# Environment — copy from the root template and edit as needed
copy ..\.env.example .env           # Windows (or `cp ../.env.example .env`)

# Database
python -m alembic -c alembic/alembic.ini upgrade head

# Run
start.bat                           # uvicorn on http://localhost:8001
```

The API docs are available at http://localhost:8001/docs after starting.

> Tip: resume uploads and AI generation degrade gracefully without keys — set
> `OPENAI_API_KEY` in `.env` to enable LLM-powered cover letters, interview
> questions, and analytics insights.

## Frontend setup

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8001`; the API client
defaults to `http://localhost:8001` (override with `VITE_API_URL`).

## Environment variables

See `.env.example` for the full list. Key ones:

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | SQLAlchemy database URL (default `sqlite:///./jobcopilot.db`) |
| `OPENAI_API_KEY` | Enables LLM features (cover letters, interview Q&A, insights) |
| `SECRET_KEY` | JWT signing key (change in production) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Job ingestion from Adzuna |
| `RAPIDAPI_KEY` | Job ingestion from jSearch |
| `CELERY_BROKER_URL` / `REDIS_URL` | Celery broker (defaults to local Redis) |

Without a running Redis broker, background tasks (e.g. resume parsing) execute
inline automatically.

## Background tasks (optional)

```bash
cd backend
celery -A app.tasks worker -l info
celery -A app.tasks beat -l info
```

## Tests and quality checks

```bash
cd backend
pytest                 # API + auth + security test suite (SQLite, isolated per test)
ruff check app alembic tests
ruff format --check app alembic tests
mypy app/

cd ../frontend
npm run lint
npm run build          # runs tsc -b && vite build
```

## API overview

- `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`
- `GET /users/me`, `PATCH /users/me`
- `POST /resumes/upload`, `GET /resumes`, `GET /resumes/{id}`, `DELETE /resumes/{id}`
- `GET /jobs/search`, `GET /jobs/suggestions`, `POST /jobs/{id}/save`
- `GET|POST|PATCH|DELETE /applications`
- `GET|POST|PATCH|DELETE /cover-letters`
- `GET|POST|DELETE /interviews/questions`
- `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/read-all`
- `GET /analytics/me`
- `GET /admin/users`, `GET /admin/ai-logs`, `GET /admin/activity-logs` (superuser only)

## License

Private project.
