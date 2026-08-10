# Environment

## Layout

- **Backend** — FastAPI app in `backend/`, own venv at `backend/.venv`, config via `backend/.env`.
- **Frontend** — React+Vite app in `frontend/`.
- **Infra** — `infra/`.

## Backend setup

```powershell
# from backend/
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # or your package-manager file
```

## Environment variables (`backend/.env` — git-ignored)

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./jobcopilot.db` |
| `OPENAI_API_KEY` | LLM provider key | Groq key |
| `OPENAI_BASE_URL` | OpenAI-compatible base | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Model id | `llama-3.1-8b-instant` |
| `RAPIDAPI_KEY` | JSearch job source | your RapidAPI key |
| `FRONTEND_URL` | CORS / redirect base | `http://localhost:5173` |
| `ENABLE_BACKGROUND_JOB_REFRESH` | Run live-job refresh loop on startup | `true` (set `false` in tests) |

A template lives at the repo root: `.env.example`. Copy it to `backend/.env` and fill real values.

### Secrets policy

- `.env` is in `.gitignore`. Never commit it, never paste a key into a chat/log/commit message.
- The values currently in `backend/.env` are your own keys. **Rotate both if they were ever exposed**
  (pasteboard, screenshots, shared files).

## Frontend setup

```powershell
# from frontend/
npm install
```

- `VITE_API_URL` (default `http://localhost:8001`) — API base for the axios client.

## Run

```powershell
# terminal 1 — backend (defaults to port 8001)
cd backend
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001

# terminal 2 — frontend
cd frontend
npm run dev        # http://localhost:5173
```

## Verify (must be green before shipping a phase)

```powershell
# backend
cd backend
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check app
& .\.venv\Scripts\python.exe -m mypy app

# frontend
cd frontend
npm run lint
npm run build
```

## Migrations

```powershell
cd backend
& .\.venv\Scripts\python.exe -m alembic upgrade head
```

Migrated to `0003` (`password_reset_tokens`); the existing DB is stamped at head and `alembic check` reports
no drift.
