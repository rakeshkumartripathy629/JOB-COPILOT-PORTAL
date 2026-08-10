import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  AlertTriangle,
  Bookmark,
  Briefcase,
  Building2,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Globe,
  Loader2,
  MapPin,
  Pencil,
  Play,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import {
  JobSearchResult,
  SearchHistoryItem,
  SearchProfileResponse,
  SearchResultsResponse,
  SearchSessionStatus,
} from '../types'
import { Button } from '../components/ui/button'
import { cn } from '../utils/cn'
import { MatchDetailsModal } from '../components/jobs/MatchDetailsModal'

type TimeRange = '1h' | '24h' | '3d' | '7d' | 'any'

const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '1h', label: 'Last 1 hour' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '3d', label: 'Last 3 days' },
  { value: '7d', label: 'Last 7 days' },
  { value: 'any', label: 'Any time' },
]

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: '₹',
  USD: '$',
  EUR: '€',
  GBP: '£',
  AUD: 'A$',
  CAD: 'C$',
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const diff = Date.now() - t
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatSalary(job: JobSearchResult): string {
  const symbol = CURRENCY_SYMBOLS[job.salary_currency ?? ''] ?? ''
  const min = job.salary_min
  const max = job.salary_max
  if (min === null && max === null) return ''
  if (max === null) return `${symbol}${(min ?? 0).toLocaleString()}`
  if (min === null) return `${symbol}${max.toLocaleString()}`
  return `${symbol}${min.toLocaleString()} – ${symbol}${max.toLocaleString()}`
}

function matchColor(score: number): string {
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#0ea5e9'
  return '#f59e0b'
}

function MatchRing({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(score)))
  const color = matchColor(pct)
  return (
    <div
      className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${color} ${pct}%, var(--border, #e5e7eb) ${pct}% 100%)` }}
      title={`${pct}% match`}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-background text-sm font-bold tabular-nums">
        {pct}
      </div>
    </div>
  )
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors',
        checked ? 'bg-primary' : 'bg-input'
      )}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 transform rounded-full bg-background shadow-sm transition-transform',
          checked ? 'translate-x-[1.125rem]' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

export default function JobsPage() {
  const qc = useQueryClient()
  const [timeRange, setTimeRange] = useState<TimeRange>('any')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [matchMin, setMatchMin] = useState(0)
  const [freeText, setFreeText] = useState('')
  const [activeSearchId, setActiveSearchId] = useState<number | null>(null)
  const [activeStatus, setActiveStatus] = useState<SearchSessionStatus | null>(null)
  const [results, setResults] = useState<SearchResultsResponse | null>(null)
  const [pollError, setPollError] = useState('')
  const [searchError, setSearchError] = useState('')
  const [matchJobId, setMatchJobId] = useState<number | null>(null)

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['jobs-profile'],
    queryFn: async () => (await api.get('/jobs/profile')).data as SearchProfileResponse,
  })

  const { data: history } = useQuery({
    queryKey: ['search-history'],
    queryFn: async () => (await api.get('/jobs/searches')).data as SearchHistoryItem[],
    enabled: !!profile?.has_resume,
  })

  const { data: apps } = useQuery({
    queryKey: ['apps'],
    queryFn: async () => {
      const { data } = await api.get('/applications')
      return data as { job_id: number }[]
    },
  })

  const hasResume = profile?.has_resume ?? false
  const savedIds = new Set(apps?.map((a) => a.job_id) ?? [])

  useEffect(() => {
    if (activeSearchId === null) return
    let stopped = false
    let timer: number | undefined

    async function tick() {
      if (stopped) return
      try {
        const { data: status } = await api.get<SearchSessionStatus>(
          `/jobs/search/${activeSearchId}/status`
        )
        if (stopped) return
        setActiveStatus(status)
        setPollError('')
        if (status.status === 'COMPLETED' || status.status === 'FAILED') {
          const params: Record<string, unknown> = {}
          if (timeRange !== 'any') params.time_range = timeRange
          if (matchMin > 0) params.match_min = matchMin
          const { data } = await api.get<SearchResultsResponse>(
            `/jobs/search/${activeSearchId}`,
            { params }
          )
          if (!stopped) {
            setResults(data)
            qc.invalidateQueries({ queryKey: ['search-history'] })
          }
          return
        }
      } catch (err) {
        if (!stopped) setPollError(getApiError(err))
        return
      }
      timer = window.setTimeout(tick, 1500)
    }

    tick()
    return () => {
      stopped = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [activeSearchId, timeRange, matchMin, qc])

  const runSearch = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ search_id: number; status: string }>('/jobs/search', {
        time_range: timeRange,
        remote: 'any',
      })
      return data.search_id
    },
    onSuccess: (searchId) => {
      setSearchError('')
      setResults(null)
      setActiveStatus(null)
      setActiveSearchId(searchId)
      toast.success('Live search started — finding fresh jobs on the internet')
    },
    onError: (err) => {
      setSearchError(getApiError(err))
      setActiveStatus(null)
      setActiveSearchId(null)
    },
  })

  const deleteSearch = useMutation({
    mutationFn: async (searchId: number) => {
      await api.delete(`/jobs/search/${searchId}`)
      return searchId
    },
    onSuccess: (searchId) => {
      toast.success('Search removed from history')
      if (activeSearchId === searchId) {
        setActiveSearchId(null)
        setActiveStatus(null)
        setResults(null)
      }
      qc.invalidateQueries({ queryKey: ['search-history'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const toggleSave = useMutation({
    mutationFn: async (jobId: number) => {
      const saved = savedIds.has(jobId)
      if (saved) {
        await api.delete(`/jobs/${jobId}/save`)
      } else {
        await api.post(`/jobs/${jobId}/save`)
      }
      return !saved
    },
    onSuccess: (saved) => {
      toast.success(saved ? 'Job saved' : 'Job removed from saved')
      qc.invalidateQueries({ queryKey: ['apps'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const viewingHistory = (id: number) => {
    setSearchError('')
    setResults(null)
    setActiveStatus(null)
    setActiveSearchId(id)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const displayedJobs = (results?.jobs ?? []).filter((job) => {
    if (remoteOnly && !isRemote(job)) return false
    if (freeText) {
      const q = freeText.toLowerCase()
      const hay = `${job.title} ${job.company_name ?? ''} ${job.skills_required ?? ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })

  return (
    <div className="space-y-8 animate-in">
      <header>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Jobs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Discover jobs that match your resume — found live on the internet.
        </p>
      </header>

      {profileLoading ? (
        <div className="card flex items-center justify-center gap-3 p-10 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Building your job profile…
        </div>
      ) : !hasResume ? (
        <EmptyState />
      ) : (
        <>
          <ProfileCard profile={profile} />

          <section className="card space-y-4 p-4 shadow-soft sm:p-5">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[12rem] flex-1">
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Search within results</label>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={freeText}
                    onChange={(e) => setFreeText(e.target.value)}
                    placeholder="e.g. react, remote, fintech"
                    className="input pl-8"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Posted</label>
                <select
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value as TimeRange)}
                  className="input w-auto cursor-pointer"
                  aria-label="Time range"
                >
                  {TIME_RANGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2 pb-1.5">
                <Toggle checked={remoteOnly} onChange={setRemoteOnly} label="Remote only" />
                <span className="text-sm">Remote only</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-[16rem] flex-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <label htmlFor="match-slider">Minimum match</label>
                  <span className="font-semibold text-foreground">{matchMin}%</span>
                </div>
                <input
                  id="match-slider"
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={matchMin}
                  onChange={(e) => setMatchMin(Number(e.target.value))}
                  className="mt-1 w-full accent-primary"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button onClick={() => runSearch.mutate()} disabled={runSearch.isPending}>
                  <Play className="h-4 w-4" />
                  {runSearch.isPending ? 'Starting…' : 'Search Jobs'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => runSearch.mutate()}
                  disabled={runSearch.isPending}
                  title="Run a fresh live search right now"
                >
                  <RefreshCw className={cn('h-4 w-4', runSearch.isPending && 'animate-spin')} />
                  Refresh Jobs
                </Button>
              </div>
            </div>
          </section>

          {searchError && (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {searchError}
            </p>
          )}

          {activeStatus?.status === 'SEARCHING' && (
            <LiveStatusPanel status={activeStatus} />
          )}

          {activeStatus?.status === 'FAILED' && (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {activeStatus.error ?? 'This search failed. Try again.'}
            </p>
          )}

          {pollError && (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-600 dark:text-amber-400">
              {pollError}
            </p>
          )}

          {results ? (
            <ResultsSection
              displayed={displayedJobs}
              total={results.jobs.length}
              savedIds={savedIds}
              onToggleSave={toggleSave.mutate}
              onRerun={() => runSearch.mutate()}
              onViewMatch={setMatchJobId}
            />
          ) : (
            !activeSearchId && !searchError && !activeStatus && (
              <section className="card flex items-start gap-4 p-5 shadow-soft">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="space-y-1 text-sm text-muted-foreground">
                  <p className="font-medium text-foreground">Ready when you are</p>
                  <p>
                    Hit <span className="font-semibold text-foreground">Search Jobs</span> to scan
                    live job boards with the roles &amp; skills extracted from your resume. Fresh
                    results usually land within 5–10 seconds.
                  </p>
                  <p className="text-xs">
                    Sources: Greenhouse, Ashby, Remotive, Arbeitnow &amp; more. Some portals are
                    surfaceable via Google search only and return honestly "unavailable" here.
                  </p>
                </div>
              </section>
            )
          )}

          {history && history.length > 0 && (
            <HistorySection
              history={history}
              activeSearchId={activeSearchId}
              onView={viewingHistory}
              onDelete={deleteSearch.mutate}
              deleting={deleteSearch.isPending}
            />
          )}
        </>
      )}

      {matchJobId !== null && <MatchDetailsModal jobId={matchJobId} onClose={() => setMatchJobId(null)} />}
    </div>
  )
}

function isRemote(job: JobSearchResult): boolean {
  if (job.remote_type === 'Remote') return true
  if (/remote/i.test(job.location ?? '')) return true
  return false
}

function EmptyState() {
  return (
    <section className="card flex flex-col items-center gap-4 p-10 text-center shadow-soft">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <FileText className="h-8 w-8" />
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">You don't have a resume yet</h2>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">
          We'll scan your resume to build your job profile, then search the live internet for
          fresh openings that truly fit you.
        </p>
      </div>
      <Link to="/resume">
        <Button>
          <FileText className="h-4 w-4" />
          Upload Resume
        </Button>
      </Link>
    </section>
  )
}

function ProfileCard({ profile }: { profile: SearchProfileResponse | undefined }) {
  const p = profile?.profile
  return (
    <section className="card space-y-3 p-5 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Briefcase className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold">Your Job Profile</h2>
            <p className="text-sm text-muted-foreground">
              Built from your resume — edits go to your resume.
            </p>
          </div>
        </div>
        <Link to="/resume" title="Edit resume">
          <Button variant="ghost" size="icon">
            <Pencil className="h-4 w-4" />
          </Button>
        </Link>
      </div>

      {!p ? (
        <p className="text-sm text-muted-foreground">Profile is being built…</p>
      ) : (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Designation</p>
            <p className="truncate font-semibold">{p.designation ?? 'Professional'}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Experience</p>
            <p className="font-semibold">
              {p.experienceYears !== null && p.experienceYears !== undefined
                ? `${p.experienceYears} yrs`
                : 'TBD'}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Locations</p>
            <p className="font-semibold">{p.locations?.length ? p.locations.join(', ') : 'Anywhere'}</p>
          </div>
          {p.seniority && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Seniority</p>
              <p className="font-semibold">{p.seniority}</p>
            </div>
          )}
          {p.workMode && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Work mode</p>
              <p className="font-semibold">{p.workMode}</p>
            </div>
          )}
          <div className="w-full">
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Target roles &amp; skills
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(p.roles ?? []).slice(0, 4).map((role) => (
                <span key={role} className="badge bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary">
                  {role}
                </span>
              ))}
              {(p.skills ?? []).slice(0, 8).map((skill) => (
                <span key={skill} className="badge bg-muted text-muted-foreground">
                  {skill}
                </span>
              ))}
              {(p.skills ?? []).length > 8 && (
                <span className="badge bg-muted text-muted-foreground">
                  +{(p.skills ?? []).length - 8} more
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

const SOURCE_ICONS: Record<string, 'linkedin' | 'building' | 'globe'> = {
  linkedin: 'linkedin',
  greenhouse: 'building',
}

function SourceIcon({ name }: { name: string }) {
  const kind = SOURCE_ICONS[name.toLowerCase()] ?? 'globe'
  if (kind === 'linkedin') return <LinkedinIcon className="h-3.5 w-3.5" />
  if (kind === 'building') return <Building2 className="h-3.5 w-3.5" />
  return <Globe className="h-3.5 w-3.5" />
}

function LinkedinIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.55C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.72C24 .77 23.2 0 22.22 0z" />
    </svg>
  )
}

function LiveStatusPanel({ status }: { status: SearchSessionStatus }) {
  const done = status.sources.filter((s) => s.status === 'SUCCESS' || s.status === 'EMPTY').length
  return (
    <section className="card space-y-4 p-5 shadow-soft">
      <div className="flex items-center gap-3">
        <div className="relative flex h-10 w-10 items-center justify-center">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/30" />
          <span className="relative flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </span>
        </div>
        <div>
          <h2 className="text-base font-semibold">Searching live jobs on the internet</h2>
          <p className="text-sm text-muted-foreground">
            Scanning {status.sources.length} sources · {done} done · usually takes 5–10 seconds
          </p>
        </div>
      </div>
      {status.queries.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Queries: {status.queries.slice(0, 4).join(' · ')}
        </p>
      )}
      <div className="space-y-1.5">
        {status.sources.map((s) => (
          <div key={s.name} className="flex items-center gap-2 text-sm">
            <SourceIcon name={s.name} />
            <span className="min-w-0 flex-1 truncate font-medium">{s.portal ?? s.name}</span>
            {s.status === 'SUCCESS' && (
              <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> {s.count} jobs
              </span>
            )}
            {s.status === 'EMPTY' && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5" /> 0 new
              </span>
            )}
            {s.status === 'SEARCHING' && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> searching…
              </span>
            )}
            {(s.status === 'ERROR' || s.status === 'UNAVAILABLE' || s.status === 'RATE_LIMITED') && (
              <span
                className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"
                title={s.error ?? ''}
              >
                <AlertTriangle className="h-3.5 w-3.5" /> {s.status === 'UNAVAILABLE' ? 'unavailable' : 'error'}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function ResultsSection({
  displayed,
  total,
  savedIds,
  onToggleSave,
  onRerun,
  onViewMatch,
}: {
  displayed: JobSearchResult[]
  total: number
  savedIds: Set<number>
  onToggleSave: (jobId: number) => void
  onRerun: () => void
  onViewMatch: (jobId: number) => void
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h2 className="text-lg font-semibold">
            Jobs found
            <span className="ml-1.5 text-sm font-normal text-muted-foreground">
              {total} {total === 1 ? 'result' : 'results'} · showing {displayed.length}
            </span>
          </h2>
        </div>
        <Button variant="outline" size="sm" onClick={onRerun}>
          <RefreshCw className="h-3.5 w-3.5" />
          Run again
        </Button>
      </div>
      <div className="grid gap-4">
        {displayed.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            saved={savedIds.has(job.id)}
            onToggleSave={() => onToggleSave(job.id)}
            onViewMatch={() => onViewMatch(job.id)}
          />
        ))}
        {displayed.length === 0 && (
          <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            No jobs match these filters. Loosen the time range or minimum match, or run a fresh search.
          </p>
        )}
      </div>
    </section>
  )
}

function JobCard({
  job,
  saved,
  onToggleSave,
  onViewMatch,
}: {
  job: JobSearchResult
  saved: boolean
  onToggleSave: () => void
  onViewMatch: () => void
}) {
  const salary = formatSalary(job)
  const posted = job.posting_verified ? timeAgo(job.posted_at) : timeAgo(job.discovered_at)
  const applyUrl = job.application_url || job.canonical_url || job.source_url || ''
  const distinctSources = Array.from(new Set(job.source_references.map((r) => r.source).filter(Boolean)))

  return (
    <div className="card p-5 shadow-soft transition-all duration-200 hover:shadow-lift">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {job.rank !== null && job.rank !== undefined && (
              <span className="badge bg-muted font-semibold tabular-nums">#{job.rank}</span>
            )}
            <h3 className="text-base font-semibold leading-snug">{job.title}</h3>
            {job.recommendation && (
              <span className="badge bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                {job.recommendation}
              </span>
            )}
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-muted-foreground">
            <Briefcase className="h-3.5 w-3.5 shrink-0" />
            {job.company_name ?? 'Unknown'}
            {job.location && (
              <>
                <span className="text-border">·</span>
                <MapPin className="h-3.5 w-3.5 shrink-0" />
                {job.location}
              </>
            )}
            {job.country && job.country !== job.location && (
              <>
                <span className="text-border">·</span>
                {job.country}
              </>
            )}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            {job.job_type && <span className="badge bg-secondary text-secondary-foreground">{job.job_type}</span>}
            {job.seniority && <span className="badge bg-muted text-muted-foreground">{job.seniority}</span>}
            {salary && <span className="font-medium text-emerald-600 dark:text-emerald-400">{salary}</span>}
            {posted && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3.5 w-3.5" />
                {posted}
                {!job.posting_verified && (
                  <span className="badge bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary">New</span>
                )}
              </span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {job.matched_skills.slice(0, 6).map((skill) => (
              <span
                key={skill}
                className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
              >
                {skill}
              </span>
            ))}
            {job.missing_skills.slice(0, 6).map((skill) => (
              <span
                key={skill}
                className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
                title="Missing from your resume"
              >
                {skill}
              </span>
            ))}
            {job.matched_skills.length > 6 && (
              <span className="text-xs text-muted-foreground">+{job.matched_skills.length - 6} more</span>
            )}
          </div>

          <p className="mt-2 text-xs text-muted-foreground">
            Skills {job.skill_score} · Experience {job.experience_score} · Seniority {job.seniority_score} · Location{' '}
            {job.location_score} · Salary {job.salary_score}
            {job.rank_explanation ? ` — ${job.rank_explanation}` : ''}
          </p>

          {distinctSources.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {distinctSources.slice(0, 3).map((src) => (
                <span key={src} className="flex items-center gap-1 text-xs text-muted-foreground">
                  <SourceIcon name={src} />
                  {src}
                </span>
              ))}
              {distinctSources.length > 3 && (
                <span className="text-xs text-muted-foreground">+{distinctSources.length - 3}</span>
              )}
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-center gap-2">
          <MatchRing score={job.match_score} />
          <span className="text-xs font-medium text-muted-foreground">match</span>
          {job.match_confidence !== null && job.match_confidence !== undefined && (
            <span className="badge bg-muted text-muted-foreground" title="Confidence of the match score">
              {job.match_confidence}% conf
            </span>
          )}
          {job.requirements && (
            <div className="flex flex-wrap justify-center gap-1">
              {job.requirements.met > 0 && (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                  {job.requirements.met} met
                </span>
              )}
              {job.requirements.related > 0 && (
                <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                  {job.requirements.related} related
                </span>
              )}
              {job.requirements.partial > 0 && (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                  {job.requirements.partial} partial
                </span>
              )}
              {job.requirements.missing > 0 && (
                <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-500/15 dark:text-red-300">
                  {job.requirements.missing} missing
                </span>
              )}
            </div>
          )}
          <Button variant="outline" size="sm" onClick={onViewMatch} title="Open the advanced match analysis">
            <Sparkles className="h-3.5 w-3.5" />
            Match details
          </Button>
          <Button
            variant={saved ? 'secondary' : 'outline'}
            size="sm"
            onClick={onToggleSave}
            title={saved ? 'Remove from saved' : 'Save job'}
          >
            <Bookmark className={cn('h-3.5 w-3.5', saved && 'fill-current')} />
            {saved ? 'Saved' : 'Save'}
          </Button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <a href={applyUrl} target="_blank" rel="noreferrer" className="inline-flex">
          <Button size="sm">
            Apply on {job.source ?? 'Source'}
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        </a>
        {job.source_references
          .filter((ref) => ref.source_url && ref.source_url !== applyUrl)
          .slice(0, 2)
          .map((ref) => (
            <a key={`${ref.source}-${ref.source_url}`} href={ref.source_url} target="_blank" rel="noreferrer">
              <Button size="sm" variant="outline">
                Apply on {ref.source}
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </a>
          ))}
        {job.source_references.filter((ref) => ref.source_url && ref.source_url !== applyUrl).length > 2 && (
          <span className="text-xs text-muted-foreground">
            +{job.source_references.filter((ref) => ref.source_url && ref.source_url !== applyUrl).length - 2} more sources
          </span>
        )}
      </div>
    </div>
  )
}

function HistorySection({
  history,
  activeSearchId,
  onView,
  onDelete,
  deleting,
}: {
  history: SearchHistoryItem[]
  activeSearchId: number | null
  onView: (id: number) => void
  onDelete: (id: number) => void
  deleting: boolean
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Search history</h2>
      <div className="grid gap-3">
        {history.map((item) => {
          const active = item.search_id === activeSearchId
          return (
            <div
              key={item.search_id}
              className={cn(
                'card flex flex-wrap items-center gap-3 p-4 shadow-soft',
                active && 'ring-2 ring-primary/60'
              )}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <Clock className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-x-2 text-sm">
                  <span className="font-medium">{timeAgo(item.created_at)}</span>
                  <span className="badge bg-muted text-muted-foreground">
                    {item.time_range === 'any' ? 'any time' : `last ${item.time_range}`}
                  </span>
                  {item.status === 'COMPLETED' && (
                    <span className="badge bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                      {item.result_count} results
                    </span>
                  )}
                  {item.status !== 'COMPLETED' && (
                    <span className="badge bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                      {item.status.toLowerCase()}
                    </span>
                  )}
                </p>
                {item.queries.length > 0 && (
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {item.queries.slice(0, 3).join(' · ')}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {item.status === 'COMPLETED' && (
                  <Button variant={active ? 'default' : 'outline'} size="sm" onClick={() => onView(item.search_id)}>
                    <Search className="h-3.5 w-3.5" />
                    {active ? 'Viewing' : 'View'}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onDelete(item.search_id)}
                  disabled={deleting}
                  title="Delete this search"
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
