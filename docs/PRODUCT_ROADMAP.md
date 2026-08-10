# Product Roadmap — AI Job Copilot

A complete job-search assistant: real job aggregation, AI resume parsing / cover letters / interview prep,
application tracking, and application automation — no dummy data anywhere.

## Product goals (hard requirements)

1. Every feature must use real data from the real DB or real external APIs. **No mock/dummy/hardcoded data.**
2. All AI features go through the configured LLM provider (OpenAI-compatible, currently Groq).
3. All job listings are either scraped from real free sources (Remotive, JSearch, Jobicy, Arbeitnow) or
   created by the user — never seeded with fake rows.
4. Build must stay green: `pytest`, `ruff`, `mypy` (backend) and `lint` + `build` (frontend).

## Feature checklist (spec → status)

Legend: ✅ complete · 🔶 partial/buggy · ❌ missing

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Register / login (JWT access + refresh) | ✅ | Access+refresh via httpOnly cookie; auto-refresh interceptor |
| 2 | Logout (revokes refresh token) | ✅ | |
| 3 | Forgot password / reset | 🔶 | Endpoint + `password_reset_tokens` model exist, but the table has **no migration** (drift) |
| 4 | Email verification | ❌ | Not implemented |
| 5 | User profile (headline, phone, location, summary, links) | ✅ | `profiles` table, PATCH `/users/me/profile` |
| 6 | Job CRUD (admin-created) | ✅ | |
| 7 | Job aggregation from live sources | ✅ | Remotive + JSearch (RapidAPI) + Jobicy + Arbeitnow, refresh via CLI/schedule |
| 8 | Job search / filters (title, location, type, source, salary) | ✅ | |
| 9 | Save jobs / track saved state | ✅ | ApplicationStatus.SAVED |
| 10 | Applications (status pipeline: SAVED → APPLIED → INTERVIEW → OFFER / REJECTED) | ✅ | |
| 11 | Application notes / reminders | ✅ | |
| 12 | Resume upload + parsing | ✅ | PDF/DOCX text extraction + AI normalization |
| 13 | Resume edit + versioning | ✅ | `resume_versions` table |
| 14 | ATS score / match analysis | ✅ | LLM-assisted score + reason in `job_match_agent` (heuristic pre-filter + fallback) |
| 15 | Cover letter generation | ✅ | LLM |
| 16 | Interview question generation | ✅ | LLM, per-job |
| 17 | Mock interview answers | ✅ | LLM answer evaluation: score, strengths, improvements, model answer |
| 18 | Job match scores (AI) | ✅ | LLM-scored, see #14 |
| 19 | Analytics dashboard | ✅ | Counts + insights endpoint |
| 20 | Notifications | ✅ | DB-backed |
| 21 | Admin panel | ✅ | User/job management endpoints + page |
| 22 | Application automation (analyze page + autofill draft) | 🔶 | Works but has 3 known bugs (see IMPLEMENTATION_STATUS) |
| 23 | Real (not simulated) form submission | ❌ | Deliberately out of scope; user manually submits |

## Execution phases

Executed strictly in order. Each phase ends green (lint/type/test/build) and is reviewed before the next starts.

- **Phase 0 — Audit & documentation** ✅: repository audit, this roadmap, architecture/DB/AI docs,
  implementation-status matrix, env guide.
- **Phase 1 — Critical bug fixes** ✅: automation `Profile` import, `get_by_token` removal, SSRF guard in
  `analyze_page` (12 tests), `password_reset_tokens` migration `0003`, alembic stamped at head (no drift),
  test flakiness fixed (`ENABLE_BACKGROUND_JOB_REFRESH` off in tests), `ruff` + `mypy` clean.
- **Phase 3 — Real feature gap fill** *(next)*: email verification, password reset end-to-end verification.
  (mock-interview answer evaluation and ATS-grade LLM match scoring shipped early — see below.)
- **Phase 4 — Hardening & ops**: rate limits, admin guard improvements, structured logging, CI (lint + typecheck +
  test + build on every change), secrets hygiene.

Current state: **AI-live — 53 backend tests pass, ruff/mypy clean, frontend lint/build clean. Job match scoring
and interview answer evaluation run against a real LLM (Groq), verified live. No dummy data anywhere.**
