# Job Sources

Every job listing in the system is acquired through a registered `JobSource` in
`backend/app/services/job_sources/`. Each source is honest about **how** it acquired a
listing (`source_method`) and **how exact** its posting time is (`posted_at_precision`).
Nothing is invented: if a portal is not integrated, that portal reports `UNAVAILABLE`
with the real reason instead of returning fake data.

## Source methods

| Method | Meaning |
|--------|---------|
| `OFFICIAL_API` | Documented portal API with credentials (Adzuna, JSearch) |
| `AUTHORIZED_FEED` | Public/official feed or board API, no keys (Remotive, Arbeitnow, Greenhouse, Ashby) |
| `PUBLIC_SEARCH_DISCOVERY` | Found via Google Custom Search, never via the portal itself (LinkedIn, Wellfound, Instahyre, Naukri, Google Search) |
| `PUBLIC_PAGE` | Parsed directly from a public portal page |
| `UNKNOWN` | Acquisition method not asserted |

## Registered sources

| Name | Portal | Method | Keys |
|------|--------|--------|------|
| `google_cse` | Google Search | `PUBLIC_SEARCH_DISCOVERY` | `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` |
| `linkedin` | LinkedIn | `PUBLIC_SEARCH_DISCOVERY` | `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` |
| `wellfound` | Wellfound | `PUBLIC_SEARCH_DISCOVERY` | `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` |
| `instahyre` | Instahyre | `PUBLIC_SEARCH_DISCOVERY` | `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` |
| `naukri` | Naukri | `PUBLIC_SEARCH_DISCOVERY` | `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` |
| `adzuna` | Adzuna | `OFFICIAL_API` | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` |
| `jsearch` | JSearch | `OFFICIAL_API` | `RAPIDAPI_KEY` |
| `greenhouse` | Greenhouse | `AUTHORIZED_FEED` | none |
| `ashby` | Ashby | `AUTHORIZED_FEED` | none |
| `remotive` | Remotive | `AUTHORIZED_FEED` | none |
| `arbeitnow` | Arbeitnow | `AUTHORIZED_FEED` | none |

The four `PUBLIC_SEARCH_DISCOVERY` portals (LinkedIn, Wellfound, Instahyre, Naukri) each have a
dedicated adapter that scopes one Google Custom Search query with a `site:` operator
(e.g. `site:linkedin.com/jobs`). Google is a discovery index only — timestamps and details come
from the real portal pages, never invented. When `GOOGLE_API_KEY`/`GOOGLE_CSE_ID` are not set,
these sources report `UNAVAILABLE` with "not configured".

## Where the metadata lives

- `jobs.source_method`, `jobs.source_portal`, `jobs.posted_at_precision`
- `job_source_references.source_method`, `source_portal`, `posted_at_precision` (per occurrence)
- `search_source_statuses.source_method` (recorded at search time)
- Migrations: `0009_add_source_method`

## API

- `GET /jobs/sources/status` — real availability + method of every registered source:
  `{name, display_name, portal, source_method, available, requires_config}`.
- `POST /jobs/search/{id}/refresh` — re-runs a finished search session against live sources
  (resets status, clears stale results, schedules a new background run).
- Search status (`GET /jobs/search/{id}/status`) reports real per-source states
  (`SEARCHING`/`SUCCESS`/`EMPTY`/`UNAVAILABLE`/`RATE_LIMITED`/`ERROR`) with counts.
- Result cards carry `source_method`, `source_portal`, `posted_at_precision`, and
  per-reference metadata in `source_references`.

## Time filters

Filters `1h`/`24h`/`3d`/`7d` use **only** verified posting times
(`posted_at_precision` = `EXACT`/`RELATIVE`). Jobs without a real posting time
(`UNKNOWN`) surface only under "any". See `job_freshness_service.py`.
