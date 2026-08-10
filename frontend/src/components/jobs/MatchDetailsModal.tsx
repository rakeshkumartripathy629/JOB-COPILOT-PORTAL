import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  DollarSign,
  Gauge,
  Loader2,
  Sparkles,
  Target,
  X,
} from 'lucide-react'
import api from '../../services/api'
import {
  AdvancedMatch,
  JobMatchEvidenceRecord,
  RoiResponse,
  ShouldApplyResponse,
} from '../../types'
import { Button } from '../ui/button'
import { cn } from '../../utils/cn'

type Tab = 'match' | 'evidence' | 'should-apply' | 'roi'

const CLASS_LABELS: Record<string, { label: string; cls: string }> = {
  DIRECT_MATCH: { label: 'Direct', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300' },
  RELATED_MATCH: { label: 'Related', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300' },
  PARTIAL_MATCH: { label: 'Partial', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300' },
  NO_EVIDENCE: { label: 'No evidence', cls: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' },
}

function scoreColor(value: number): string {
  if (value >= 75) return 'text-emerald-600 dark:text-emerald-400'
  if (value >= 50) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col rounded-xl bg-muted/50 p-3">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className={cn('text-lg font-bold tabular-nums', scoreColor(value))}>{value}</span>
    </div>
  )
}

export function MatchDetailsModal({ jobId, onClose }: { jobId: number; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('match')

  const match = useQuery({
    queryKey: ['job-match', jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/match`)).data as AdvancedMatch,
  })
  const evidence = useQuery({
    queryKey: ['job-evidence', jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/evidence`)).data as JobMatchEvidenceRecord[],
    enabled: tab === 'evidence',
  })
  const shouldApply = useQuery({
    queryKey: ['job-should-apply', jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/should-apply`)).data as ShouldApplyResponse,
    enabled: tab === 'should-apply',
  })
  const roi = useQuery({
    queryKey: ['job-roi', jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/roi`)).data as RoiResponse,
    enabled: tab === 'roi',
  })

  const tabs: { key: Tab; label: string }[] = [
    { key: 'match', label: 'Match analysis' },
    { key: 'evidence', label: 'Evidence' },
    { key: 'should-apply', label: 'Should I apply?' },
    { key: 'roi', label: 'Apply ROI' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Job match details"
      >
        <div className="flex items-center justify-between gap-4 border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold">Match details</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex gap-1 border-b border-border px-4 pt-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'rounded-t-lg border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                tab === t.key
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {tab === 'match' && <MatchTab match={match.data} loading={match.isLoading} error={match.isError} onRetry={match.refetch} />}
          {tab === 'evidence' && <EvidenceTab evidence={evidence.data} loading={evidence.isLoading} error={evidence.isError} onRetry={evidence.refetch} />}
          {tab === 'should-apply' && <ShouldApplyTab data={shouldApply.data} loading={shouldApply.isLoading} error={shouldApply.isError} onRetry={shouldApply.refetch} />}
          {tab === 'roi' && <RoiTab data={roi.data} loading={roi.isLoading} error={roi.isError} onRetry={roi.refetch} />}
        </div>
      </div>
    </div>
  )
}

function ErrorBox({ error, onRetry }: { error: boolean; onRetry: () => void }) {
  if (!error) return null
  return (
    <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
      Could not load this data.
      <button onClick={onRetry} className="ml-2 font-semibold underline">
        Retry
      </button>
    </div>
  )
}

function LoadingBox({ loading }: { loading: boolean }) {
  if (!loading) return null
  return (
    <div className="flex items-center justify-center gap-2 p-10 text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" /> Analyzing…
    </div>
  )
}

function MatchTab({
  match,
  loading,
  error,
  onRetry,
}: {
  match: AdvancedMatch | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}) {
  if (!match) {
    return (
      <div className="space-y-4">
        <LoadingBox loading={loading} />
        <ErrorBox error={error} onRetry={onRetry} />
        {!loading && !error && <p className="text-sm text-muted-foreground">No match data yet. Run a search first.</p>}
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Overall" value={match.overall_score} />
        <Stat label="Required skills" value={match.required_skill_score} />
        <Stat label="Preferred skills" value={match.preferred_skill_score} />
        <Stat label="Confidence" value={match.match_confidence} />
      </div>

      <div className="rounded-xl border border-border p-4">
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <Target className="h-4 w-4 text-primary" /> Requirement matrix
        </h3>
        <div className="space-y-2">
          {match.requirements.map((req) => {
            const meta = CLASS_LABELS[req.classification] ?? CLASS_LABELS.NO_EVIDENCE
            return (
              <div key={req.requirement_id} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="min-w-0 flex-1 font-medium">
                  {req.requirement}
                  {req.is_critical && (
                    <span className="ml-1.5 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-red-700 dark:bg-red-500/15 dark:text-red-300">
                      critical
                    </span>
                  )}
                </span>
                <span className={cn('rounded-md px-2 py-0.5 text-xs font-medium', meta.cls)}>{meta.label}</span>
                {req.fact_name && (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <BadgeCheck className="h-3.5 w-3.5 text-emerald-600" />
                    {req.fact_name}
                  </span>
                )}
                <span className={cn('w-8 text-right text-sm font-bold tabular-nums', scoreColor(req.skill_score))}>
                  {req.skill_score}
                </span>
              </div>
            )
          })}
        </div>
        {match.critical_missing.length > 0 && (
          <p className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            Critical gaps: {match.critical_missing.join(', ')}
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="h-4 w-4" /> Why you fit
          </h3>
          <p className="text-sm text-muted-foreground">{match.why_match}</p>
          {match.relevant_projects.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
              {match.relevant_projects.slice(0, 3).map((p) => (
                <li key={p}>• {p}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4" /> Things to watch
          </h3>
          <p className="text-sm text-muted-foreground">{match.why_not}</p>
        </div>
      </div>
    </div>
  )
}

function EvidenceTab({
  evidence,
  loading,
  error,
  onRetry,
}: {
  evidence: JobMatchEvidenceRecord[] | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}) {
  if (!evidence) {
    return (
      <div className="space-y-4">
        <LoadingBox loading={loading} />
        <ErrorBox error={error} onRetry={onRetry} />
      </div>
    )
  }
  if (evidence.length === 0) {
    return <p className="text-sm text-muted-foreground">No matched evidence for this job yet.</p>
  }
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        Every matched fact is backed by a quote from your resume — nothing is invented.
      </p>
      {evidence.map((item) => {
        const meta = CLASS_LABELS[item.classification] ?? CLASS_LABELS.NO_EVIDENCE
        return (
          <div key={item.id} className="rounded-xl border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{item.fact_name ?? 'Fact'}</span>
              {item.fact_type && (
                <span className="badge bg-muted text-muted-foreground">{item.fact_type}</span>
              )}
              <span className={cn('rounded-md px-2 py-0.5 text-xs font-medium', meta.cls)}>{meta.label}</span>
              <span className="ml-auto text-xs text-muted-foreground">conf {item.confidence}%</span>
            </div>
            {item.evidence_text && (
              <p className="mt-1.5 border-l-2 border-border pl-3 text-sm text-muted-foreground">
                “{item.evidence_text}”
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

const DECISION_STYLES: Record<string, string> = {
  STRONGLY_RECOMMENDED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  RECOMMENDED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  CONSIDER: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  LOW_PRIORITY: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  SKIP: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

function ShouldApplyTab({
  data,
  loading,
  error,
  onRetry,
}: {
  data: ShouldApplyResponse | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}) {
  if (!data) {
    return (
      <div className="space-y-4">
        <LoadingBox loading={loading} />
        <ErrorBox error={error} onRetry={onRetry} />
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className={cn('rounded-xl px-4 py-2 text-sm font-bold', DECISION_STYLES[data.decision] ?? 'bg-muted')}>
          {data.decision.replace(/_/g, ' ')}
        </span>
        <span className="text-sm text-muted-foreground">
          confidence <span className="font-bold text-foreground">{data.confidence}%</span>
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
          <h3 className="mb-2 text-sm font-semibold text-emerald-700 dark:text-emerald-300">Reasons to apply</h3>
          <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
            {data.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
          <h3 className="mb-2 text-sm font-semibold text-amber-700 dark:text-amber-400">Risks / gaps</h3>
          {data.risks.length === 0 && data.critical_gaps.length === 0 ? (
            <p className="text-sm text-muted-foreground">No major risks.</p>
          ) : (
            <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
              {[...data.critical_gaps.map((g) => `Missing critical: ${g}`), ...data.risks].map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

function RoiTab({
  data,
  loading,
  error,
  onRetry,
}: {
  data: RoiResponse | undefined
  loading: boolean
  error: boolean
  onRetry: () => void
}) {
  if (!data) {
    return (
      <div className="space-y-4">
        <LoadingBox loading={loading} />
        <ErrorBox error={error} onRetry={onRetry} />
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Gauge className={cn('h-10 w-10', scoreColor(data.roi_score))} />
        <div>
          <p className="text-3xl font-bold tabular-nums">{data.roi_score}</p>
          <p className="text-xs text-muted-foreground">out of 100 — expected value of applying</p>
        </div>
        {data.estimated_salary !== null && (
          <div className="ml-auto text-right">
            <p className="flex items-center gap-1 text-sm text-muted-foreground">
              <DollarSign className="h-4 w-4" /> estimated salary
            </p>
            <p className="text-lg font-semibold">
              {data.salary_currency} {data.estimated_salary.toLocaleString()}
            </p>
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.entries(data.signals).map(([key, value]) => (
          <span key={key} className="badge bg-muted text-muted-foreground">
            {key.replace(/_/g, ' ')}: {value}
          </span>
        ))}
      </div>
      {data.notes.length > 0 && (
        <ul className="space-y-1 text-sm text-muted-foreground">
          {data.notes.map((n) => (
            <li key={n} className="flex items-start gap-2">
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              {n}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
