# AI Architecture

## LLM provider

- **Client:** `openai.AsyncOpenAI` (OpenAI-compatible) configured in `backend/app/services/llm_service.py`.
- **Config** (`backend/app/config.py`): `OPENAI_API_KEY`, `OPENAI_BASE_URL` (currently a Groq endpoint),
  `LLM_MODEL`. The key lives in `backend/.env`; `.env` is git-ignored.
- **API:** `LLMService.generate()` (free text) and `LLMService.generate_json()` (validated JSON extraction).
  Both raise `LLMError` when the key is missing or the provider fails; callers fall back gracefully.
- Every AI call is intended to be audited via the `ai_logs` table.

### AI features and where they live

| Feature | Implementation | Real AI? |
|---------|----------------|----------|
| Resume normalization / parsing | LLM prompt over extracted text | ✅ |
| Cover letter generation | LLM | ✅ |
| Interview questions | LLM, per job | ✅ |
| Job match scoring | `job_match_agent` — heuristic pre-filter (top 20) + **LLM** semantic score 0-100 + reason; falls back to heuristic if LLM unavailable | ✅ |
| Automation page analysis | LLM prompt over fetched page text + profile | ✅ |
| Application autofill draft | LLM returns `{summary, filled[], notes[]}` | ✅ |
| Interview answer evaluation | LLM scores the answer 0-100 + strengths/improvements/model answer | ✅ |

## Agents (LangGraph)

`backend/app/agents/job_match_agent.py` — a 2-node state graph (`load_context` → `score_matches`):

- Loads the user's latest resume and up to 50 jobs with company names.
- Heuristically pre-filters to the top 20 candidates (fast, no network), then sends the resume + job summaries
  in one `LLMService.generate_json` call asking for `{id, match_score, reason}` per job.
- Returns the top 20 sorted by LLM score with a `match_reason`; if the LLM call fails, every job silently
  falls back to the heuristic word-overlap score (endpoint never 500s on LLM outage).
- **Live-verified** (Aug 2026): a Python/FastAPI resume scored 60 for "Senior Data Engineer" and 10–20 for
  non-technical roles, with a semantic reason for each.

## Job aggregation (real data)

`backend/app/services/live_jobs_service.py` + `job_search_service.py`:

- **Remotive** (`remotive.com/api/remote-jobs`) — free.
- **Jobicy** (`jobicy.com/api/v2/remote-jobs`) — free.
- **Arbeitnow** (`arbeitnow.com/api/job-board-api`) — free.
- **JSearch** (`jsearch.p.rapidapi.com/search`) — RapidAPI, gated on `RAPIDAPI_KEY`.
- `refresh_jobs()` upserts rows into `jobs`; each row keeps `source` + `source_url` so the UI can deep-link to
  the real listing. No seeded/fake jobs.

## Automation pipeline

1. `start_session` — record target `job_url`.
2. `analyze_page` — fetch page (HTML → text + form fields), load candidate profile + latest resume,
   ask the LLM to pre-fill the form, store result.
3. `confirm`/`cancel` — complete or abort the run.
- Deliberately **does not** auto-submit the form; the user submits manually.

### Automation fixes (Phase 1 — done)

1. `automation_service._build_profile` now imports the correct `Profile` model, so the candidate's profile
   fields reach the AI prompt.
2. The broken `get_by_token` (queried `RefreshToken`) was removed.
3. `_fetch_page` now blocks SSRF: http/https only, private/loopback/link-local/reserved IPs,
   `localhost`/metadata hosts, unresolvable hosts, and each redirect hop (max 5) is re-validated.
   Covered by `tests/test_automation_ssrf.py` (12 tests).

## Secret hygiene

- `backend/.env` currently contains a real Groq key and a real RapidAPI key. Both are covered by the root
  `.gitignore` (`.env`), so they are not committed. **Do not commit `.env`; rotate both keys if either was
  ever shared or pushed.**
