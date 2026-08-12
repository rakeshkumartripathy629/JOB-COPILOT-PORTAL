# Implementation Status

Verified against the running code (Aug 2026). Every feature below was checked in the source — no claims
made from memory. Goal: everything real, nothing dummy.

## Verified green checks

| Check | Result |
|-------|--------|
| Backend `pytest` | **~130 passed** (incl. 22 application + CRM tests; full suite green) |
| Backend `ruff check .` | **clean** |
| Backend `mypy app` | **clean** |
| Frontend `npm run lint` | **clean** |
| Frontend `npm run build` (`tsc -b && vite build`) | **clean** |

## Feature matrix (real vs. stub vs. missing)

| Feature | Status | Evidence |
|---------|--------|----------|
| Auth (login/register/logout/refresh) | ✅ real | `auth.py` router + service; JWT + refresh cookie; frontend interceptor retries 401 |
| Profile | ✅ real | `users.py` PATCH `/users/me/profile`, `profiles` table |
| Jobs CRUD | ✅ real | `jobs.py` |
| Live job aggregation | ✅ real | `live_jobs_service.py` (Remotive/Jobicy/Arbeitnow) + `job_search_service.py` (JSearch) |
| Job search/filters | ✅ real | query params in `jobs.py` |
| Applications pipeline | ✅ real | `applications.py` — full CRM: 15 statuses, snapshots, timeline, audit, notes, tags, reminders, follow-ups, analytics, CSV export, frozen document versions |
| Application Management + CRM | ✅ real | `application_service.py` + `applications.py` + `ApplicationDetailsPage` |
| Resume upload + parse | ✅ real | `resumes.py` + LLM normalization |
| Resume versions | ✅ real | `resume_versions` |
| Cover letters | ✅ real | `cover_letters.py` (LLM) |
| Interview questions | ✅ real | `interviews.py` (LLM) |
| Mock-interview answer evaluation | ✅ real | `POST /interviews/questions/{id}/evaluate` (LLM) + UI in `InterviewPrepPage` |
| ATS-grade match scoring | ✅ real | `job_match_agent.py` LLM scoring with heuristic pre-filter + fallback, `match_reason` |
| Advanced resume↔job match | ✅ real | `advanced_match_service.py` — deterministic, evidence-backed requirement matrix; strict classification (direct/related/partial/no-evidence); critical-gap detection; 0–100 scores + `match_confidence` |
| Career Vault (facts + evidence) | ✅ real | `career_evidence_service.py` — per-user `career_facts`/`career_evidence`; verify/confirm/reject; idempotent re-index that preserves user confirmations; rejected facts excluded from matching |
| Requirement extraction | ✅ real | `job_description_analyzer.py` — deterministic skill/education/experience extraction with REQUIRED/PREFERRED/NICE_TO_HAVE importance; persisted to `job_requirements` |
| Should-I-apply decision | ✅ real | `should_apply_service.py` — grounded in the match, never LLM; STRONGLY_RECOMMENDED…SKIP |
| Apply ROI | ✅ real | `application_roi_service.py` — 0–100 ROI from match + decision + salary + quality + freshness; never fabricates salary |
| Analytics | ✅ real | `analytics.py` counts + insights |
| Notifications | ✅ real | `notifications.py` |
| Admin | ✅ real | `admin.py` |
| Automation | 🔶 real but 3 bugs | see AI_ARCHITECTURE.md |
| Forgot password | 🔶 endpoint exists, table has no migration | `password_reset.py` model + router; DB drift |
| Email verification | ❌ missing | no flow |

## Frontend pages (all wired to real API via `services/api.ts`)

`/login`, `/signup`, `/forgot-password`, `/dashboard`, `/resume`, `/jobs`, `/vault`, `/applications`,
`/applications/:id`, `/cover-letters`, `/interview-prep`, `/automation`, `/notifications`, `/admin` + `*` NotFound.
No page contains mock/sample/dummy data (verified by scan). Dashboard and Jobs render server data only.
Jobs cards show confidence + requirement counts; the **Match details** modal renders the requirement matrix,
evidence quotes, should-apply verdict and apply-ROI. The **Career Vault** page lists every fact with its source
evidence and verify/confirm/reject controls. The **Applications** page shows live stats (total/applied/interviews/
offers/rejected/response-rate), a needs-attention queue, search/filter/sort, CSV export, and one-click status
advance; the **Application details** page has Overview (notes, priority, tags, frozen job snapshot, follow-up
status), Timeline (status history + audit log), Notes, Documents (frozen versions with HMAC-signed downloads),
Follow-up (drafted message, never auto-sent) and Reminders (create + complete) tabs.

## Bug fixes completed (Phase 1)

1. ✅ **Automation profile now loads** — `automation_service._build_profile` imports the correct `Profile`
   model; profile fields reach the AI prompt.
2. ✅ **`get_by_token` removed** — it queried the `RefreshToken` table for an `AutomationSession`; the model has
   no token column and nothing called it, so the broken method was deleted.
3. ✅ **SSRF guard** — `_fetch_page` now rejects non-http(s), private/loopback/link-local/reserved IPs,
   `localhost`/metadata hosts, unresolvable hosts, and validates every redirect hop (max 5). Covered by
   12 new tests in `tests/test_automation_ssrf.py`.
4. ✅ **`password_reset_tokens` migration** — added `0003_add_password_reset_tokens`; existing DB stamped at
   `0003`; `alembic check` reports "No new upgrade operations detected".
5. ✅ **Test flakiness fixed** — root cause: the app's background job-refresh task ran on startup
   (network + DB writes), racing the per-test DB reset and locking SQLite (`database is locked` → login 500).
   Added `ENABLE_BACKGROUND_JOB_REFRESH` setting; tests set it to `false`. Full suite now passes reliably.
6. ✅ **Lint/type debt** — `ruff` clean, `mypy` clean (fixed I001/SIM in `auth_service`/`live_jobs_service`/
   `automation_service`, `FromClause.update` → SQLAlchemy `update()`, dateutil via `types-python-dateutil`).

## AI features now live (real LLM, no dummy data)

1. ✅ **Live LLM verified** — `OPENAI_API_KEY` points at Groq (`https://api.groq.com/openai/v1`,
   `llama-3.3-70b-versatile`); a real chat completion returned expected output.
2. ✅ **AI job match scoring** — `job_match_agent` pre-filters jobs heuristically (top 20), then one batched
   LLM call scores each job 0-100 with a reason; `match_reason` shown on the Jobs page. Falls back to
   heuristic scores silently if the LLM is unavailable. Verified live: semantic scores + reasons returned.
3. ✅ **Mock-interview answer evaluation** — `POST /interviews/questions/{id}/evaluate` returns score,
   strengths, improvements, and a model answer via LLM; UI added to `InterviewPrepPage` (answer box +
   feedback). Verified live with Groq.
4. ✅ **Display bug fixed** — suggestion `match_score` was multiplied by 100 in the UI; now shown as-is.

## Remaining work (Phase 3)

- Email verification — missing.
- Verify the full forgot-password flow end-to-end (endpoints exist; SMTP path logs code when unconfigured).

## Phase 4 — Advanced match + career evidence system (live)

Deterministic, fully auditable job matching — every number shown is computed from real resume data,
never an LLM guess.

1. ✅ **Career Vault** — resume parsed into typed facts (`career_facts`: technical/soft skill, experience,
   education, certification, job title, project, achievement, location) each backed by quoted evidence
   (`career_evidence`). Confidence is lower for inferred facts (projects/achievements). Per-user isolated.
2. ✅ **Strict skill classification** (`skill_classifier.py`) — a related skill is **never** a direct match
   (MongoDB ≠ PostgreSQL, Docker ≠ Kubernetes, generic "database" ≠ PostgreSQL) and a related skill
   **never** satisfies a critical requirement. Alias canonicalization (k8s → kubernetes, aws → aws).
3. ✅ **Advanced match engine** (`advanced_match_service.py`) — builds the requirement matrix
   (direct/related/partial/no-evidence + skill score + linked fact + confidence), critical-gap detection,
   why-match/why-not, match confidence (0–100), and persists `job_requirement_matches` +
   `job_match_evidence` per (user, job).
4. ✅ **Job requirement analyzer** (`job_description_analyzer.py`) — extracts requirements from the posting
   with REQUIRED/PREFERRED/NICE_TO_HAVE importance and critical flags; stored in `job_requirements`.
5. ✅ **Should-I-apply** (`should_apply_service.py`) — decision + confidence + reasons/risks grounded in
   match scores; `STRONGLY_RECOMMENDED`/`RECOMMENDED`/`CONSIDER`/`LOW_PRIORITY`/`SKIP`.
6. ✅ **Apply ROI** (`application_roi_service.py`) — 0–100 ROI from match, decision, salary band, job quality
   and freshness; when no salary is published it says so instead of inventing a number.
7. ✅ **API surface** — `GET/POST /career/{index,summary,facts,evidence}`, `PATCH /career/facts/{id}`
   (status), `PATCH /career/evidence/{id}` (verification), `GET /jobs/{id}/match`,
   `GET /jobs/{id}/requirement-matrix`, `GET /jobs/{id}/evidence`, `GET /jobs/{id}/should-apply`,
   `GET /jobs/{id}/roi`. All user-scoped (404 for other users' records).
8. ✅ **Migration** — `0007_add_career_evidence` creates `career_facts`, `career_evidence`,
   `job_requirements`, `job_requirement_matches`, `job_match_evidence`; live DB upgraded and stamped `0007`.
9. ✅ **Tests** — 35 new tests in `tests/test_advanced_match.py` covering classification strictness,
   vault extraction/verification/isolation/idempotency, bounded scores, persistence, critical-missing
   honesty, evidence grounding, should-apply/ROI, and API access control.

## Phase 5 — Application Management + Tracking + CRM (live)

Full application lifecycle management, all persisted and user-scoped — nothing fake.

1. ✅ **15 statuses** (`DRAFT`→`READY`→`APPLIED`→`VIEWED`→`RECRUITER_CONTACT`→`ASSESSMENT`→`INTERVIEW`→
   `TECHNICAL_ROUND`→`FINAL_ROUND`→`OFFER`/`REJECTED`/`WITHDRAWN`/`EXPIRED`/`FAILED`, plus `UNKNOWN`).
   Transitions are validated (`can_transition`): terminal → reopen (`DRAFT`/`READY`, recorded in history),
   `UNKNOWN` → anything, same-status is a no-op. Invalid transition → **422**.
2. ✅ **Immutable job snapshot** — `application_snapshots` freezes title/company/location/salary/description/
   requirements/URLs/scores at creation time.
3. ✅ **Frozen document versions** — `application_documents` stores resume / tailored-resume / cover-letter
   versions used at creation; downloads via HMAC-signed URLs (24h expiry, **403** on bad token).
4. ✅ **Timeline + audit** — `application_status_history` (per-transition, with source/reason) and
   `application_audit_events` (create/update/status-change, JSON metadata).
5. ✅ **Notes, tags, reminders, follow-ups** — `application_notes`, `application_tags` (unique per user/app/
   tag), `application_reminders` (FOLLOW_UP/INTERVIEW/ASSESSMENT_DEADLINE/RECRUITER_RESPONSE, complete flow +
   notifications). Follow-up assistant recommends only after 7 days and **drafts** a message (never sends);
   `needs-attention` queue combines due follow-ups + upcoming reminders.
6. ✅ **Analytics + performance** — `GET /applications/analytics` (counts, response/interview/offer rates,
   funnel) and `/performance` (best sources/companies/locations/jobs with n≥3 suppression) — drafts excluded.
7. ✅ **Duplicate protection** — creating against an existing job/URL returns **409**.
8. ✅ **CSV export** — `GET /applications/export.csv` with tags column; wired to the frontend export button.
9. ✅ **Migration** — `0008_add_application_management` adds columns + 7 tables + indexes; legacy UPPERCASE
   statuses mapped to the new set; applied to live DB (816 jobs preserved).
10. ✅ **Tests** — `tests/test_applications.py` (rewritten) + `tests/test_applications_crm.py` = 22 tests;
    legacy `SAVED` references removed from analytics agent, jobs save/unsave (creates a real `DRAFT`
    application), and `delete_application` cleans up all CRM rows.
11. ✅ **Frontend** — `ApplicationsPage` (stats cards, needs-attention, search/filter/sort, status advance,
    delete, CSV export) and `ApplicationDetailsPage` (`/applications/:id` with Overview/Timeline/Notes/
    Documents/Follow-up/Reminders tabs), routes wired in `App.tsx`.
