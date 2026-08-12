# Database

SQLite via SQLAlchemy async; ORM models in `backend/app/db/models/`, migrations in
`backend/alembic/versions/`.

## Tables

| Model | Table | Purpose |
|-------|-------|---------|
| User | `users` | Auth + identity |
| Profile | `profiles` | 1:1 user profile (headline, phone, location, summary, links) |
| Skill | `skills` | Skills (name-unique) |
| Company | `companies` | Employers referenced by jobs |
| Job | `jobs` | Listings (title, description, requirements, skills, salary, source, source_url, job_type) |
| Application | `applications` | Full CRM lifecycle — 15 statuses (DRAFT…OFFER/REJECTED/…), source, priority, match scores, follow-up state, linked document-version IDs |
| ApplicationSnapshot | `application_snapshots` | Immutable job details frozen at application creation |
| ApplicationStatusHistory | `application_status_history` | Every status transition (old/new, source, reason, timestamp) |
| ApplicationNote | `application_notes` | Free-form notes per application |
| ApplicationTag | `application_tags` | Tags (unique per user/app/tag) |
| ApplicationReminder | `application_reminders` | FOLLOW_UP / INTERVIEW / ASSESSMENT_DEADLINE / RECRUITER_RESPONSE with due_at + status |
| ApplicationAuditEvent | `application_audit_events` | Create/update/status-change audit trail (JSON metadata) |
| ApplicationDocument | `application_documents` | Frozen resume / tailored-resume / cover-letter versions + HMAC-signed download URLs |
| Resume | `resumes` | Uploaded resume + parsed text |
| ResumeVersion | `resume_versions` | Version history per resume |
| CoverLetter | `cover_letters` | Generated letters |
| InterviewQuestion | `interview_questions` | Per-job AI questions |
| Notification | `notifications` | User notifications |
| RefreshToken | `refresh_tokens` | Rotating refresh tokens (revoked_at) |
| AutomationSession | `automation_sessions` | Application-automation runs (job_url, steps, result, status) |
| PasswordResetToken | `password_reset_tokens` | Password-reset codes (code_hash, expires_at, used) |
| ActivityLog | `activity_logs` | Audit/activity trail |
| AILog | `ai_logs` | LLM call audit |
| CareerFact | `career_facts` | Career Vault: typed facts (skill/experience/education/certification/project/achievement/…) + confidence + status + verified_by_user |
| CareerEvidence | `career_evidence` | Quoted evidence backing each fact (source section + text + confidence + verification) |
| JobRequirement | `job_requirements` | Deterministically extracted job requirements (skill, importance, critical flag) |
| JobRequirementMatch | `job_requirement_matches` | Per (user, job, requirement) match rows: classification + skill_score + linked fact |
| JobMatchEvidence | `job_match_evidence` | Persisted matched-fact evidence used in the Jobs UI |

## Migrations

Migrations now exist:

- `0001_initial_schema` — creates all core tables.
- `0002_add_automation_job_url` — adds `automation_sessions.job_url`.
- `0003_add_password_reset_tokens` — creates `password_reset_tokens` (+ indexes).
- `0004_add_live_job_search` → `0006_add_live_job_search` — live-search schema (jobs source columns,
  `job_source_references`, `job_search_sessions`, `job_search_results` + match columns).
- `0007_add_career_evidence` — creates `career_facts`, `career_evidence`, `job_requirements`,
  `job_requirement_matches`, `job_match_evidence`. The live DB is upgraded and stamped `0007`.
- `0008_add_application_management` — adds application-source/priority/follow-up/document-version columns,
  maps legacy UPPERCASE statuses to the new 15-status enum, and creates `application_snapshots`,
  `application_status_history`, `application_notes`, `application_tags`, `application_reminders`,
  `application_audit_events`, `application_documents` (+ indexes). Live DB upgraded and stamped `0008`.

**History (resolved):** `password_reset_tokens` previously had no migration, and the running DB was built by
`Base.metadata.create_all` (app startup) rather than migrations, so `alembic_version` was missing. The DB has
been stamped at `0003` and `alembic check` reports no drift, so future migrations now track cleanly.
Note: app startup still runs `create_all` — keep it, but rely on migrations for schema changes.

## Known schema issues

- `automation_sessions` uses `steps` / `result` as JSON strings (no SQLAlchemy JSON type) — functional but
  fragile.
- `datetime.utcnow` defaults are naive-UTC (deprecation warnings on Python 3.12+; removal in 3.16).
- No `ondelete` cascade / FK enforcement on some relationships — `delete_application` explicitly removes all
  CRM rows before deleting the application.

## Verification status

- Backend test suite: **~130 tests pass**, stable across repeated runs.
- The earlier analytics flakiness was caused by the app's startup job-refresh task (network + DB writes)
  racing the per-test DB reset and locking SQLite. Fixed via `ENABLE_BACKGROUND_JOB_REFRESH=false` in tests.
