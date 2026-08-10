import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  BadgeCheck,
  Database,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  XCircle,
} from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import {
  CareerEvidence,
  CareerFact,
  CareerIndexResponse,
  CareerVaultSummary,
} from '../types'
import { Button } from '../components/ui/button'
import { cn } from '../utils/cn'

const STATUS_STYLES: Record<string, string> = {
  VERIFIED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  USER_CONFIRMED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  AI_EXTRACTED: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  INFERRED: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  REJECTED: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

const FACT_TYPE_LABELS: Record<string, string> = {
  technical_skill: 'Technical skills',
  soft_skill: 'Soft skills',
  experience: 'Experience',
  education: 'Education',
  certification: 'Certifications',
  job_title: 'Job titles',
  project: 'Projects',
  achievement: 'Achievements',
  location: 'Locations',
  language: 'Languages',
}

function statusStyle(status: string): string {
  return STATUS_STYLES[status] ?? 'bg-muted text-muted-foreground'
}

function confidenceColor(value: number): string {
  if (value >= 75) return 'bg-emerald-500'
  if (value >= 50) return 'bg-amber-500'
  return 'bg-red-500'
}

export default function CareerVaultPage() {
  const qc = useQueryClient()

  const summary = useQuery({
    queryKey: ['career-summary'],
    queryFn: async () => (await api.get('/career/summary')).data as CareerVaultSummary,
  })
  const facts = useQuery({
    queryKey: ['career-facts'],
    queryFn: async () => (await api.get('/career/facts')).data as CareerFact[],
  })
  const evidence = useQuery({
    queryKey: ['career-evidence'],
    queryFn: async () => (await api.get('/career/evidence')).data as CareerEvidence[],
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['career-facts'] })
    qc.invalidateQueries({ queryKey: ['career-evidence'] })
    qc.invalidateQueries({ queryKey: ['career-summary'] })
  }

  const indexVault = useMutation({
    mutationFn: async () => (await api.post<CareerIndexResponse>('/career/index')).data,
    onSuccess: (data) => {
      toast.success(
        `${data.facts_created} new facts · ${data.facts_kept} kept · ${data.evidence_created} evidence`
      )
      invalidate()
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const updateFact = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) =>
      (await api.patch<CareerFact>(`/career/facts/${id}`, { status })).data,
    onSuccess: () => {
      toast.success('Fact updated')
      invalidate()
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const updateEvidence = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) =>
      (
        await api.patch<CareerEvidence>(`/career/evidence/${id}`, {
          verification_status: status,
        })
      ).data,
    onSuccess: () => {
      toast.success('Evidence verified')
      invalidate()
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const s = summary.data
  const byType: Record<string, CareerFact[]> = {}
  for (const f of facts.data ?? []) {
    const key = FACT_TYPE_LABELS[f.fact_type] ?? f.fact_type
    if (!byType[key]) byType[key] = []
    byType[key].push(f)
  }

  const evidenceByFact = new Map<number, CareerEvidence[]>()
  for (const e of evidence.data ?? []) {
    const list = evidenceByFact.get(e.career_fact_id)
    if (list) list.push(e)
    else evidenceByFact.set(e.career_fact_id, [e])
  }

  return (
    <div className="space-y-6 animate-in">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">
            <Database className="h-7 w-7 text-primary" />
            Career Vault
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Every skill, project, achievement and qualification the matcher uses is stored here with
            its source evidence — and you stay in control of what is (and isn't) claimed about you.
          </p>
        </div>
        <Button onClick={() => indexVault.mutate()} disabled={indexVault.isPending}>
          <RefreshCw className={cn('h-4 w-4', indexVault.isPending && 'animate-spin')} />
          {indexVault.isPending ? 'Re-indexing…' : 'Re-index resume'}
        </Button>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard label="Total facts" value={s?.facts_total} />
        <StatCard label="Verified" value={s?.facts_by_status?.VERIFIED ?? 0} />
        <StatCard label="AI-extracted" value={s?.facts_by_status?.AI_EXTRACTED ?? 0} />
        <StatCard label="Inferred" value={s?.facts_by_status?.INFERRED ?? 0} />
        <StatCard label="Evidence items" value={s?.evidence_total} />
      </div>

      {Object.entries(byType).map(([type, items]) => (
        <section key={type} className="space-y-3">
          <h2 className="text-base font-semibold">
            {type}
            <span className="ml-2 text-sm font-normal text-muted-foreground">{items.length}</span>
          </h2>
          <div className="grid gap-3 lg:grid-cols-2">
            {items.map((fact) => (
              <div key={fact.id} className="card space-y-3 p-4 shadow-soft">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold">{fact.name}</p>
                    {fact.value && fact.value !== fact.name && (
                      <p className="truncate text-sm text-muted-foreground">{fact.value}</p>
                    )}
                  </div>
                  <span className={cn('badge shrink-0', statusStyle(fact.status))}>{fact.status.replace(/_/g, ' ')}</span>
                </div>

                {fact.description && (
                  <p className="text-sm text-muted-foreground">{fact.description}</p>
                )}

                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn('h-full rounded-full', confidenceColor(fact.confidence))}
                      style={{ width: `${Math.max(0, Math.min(100, fact.confidence))}%` }}
                    />
                  </div>
                  <span className="text-xs tabular-nums text-muted-foreground">{fact.confidence}%</span>
                </div>

                {evidenceByFact.get(fact.id)?.map((ev) => (
                  <div key={ev.id} className="space-y-1.5">
                    <p className="border-l-2 border-border pl-3 text-sm text-muted-foreground">
                      “{ev.evidence_text}”
                    </p>
                    <p className="pl-3 text-[11px] text-muted-foreground">
                      {ev.source_section ?? ev.source} · {ev.confidence}% confidence
                      {ev.verified_by_user ? ' · you verified this' : ''}
                    </p>
                    {!ev.verified_by_user && (
                      <div className="pl-3">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => updateEvidence.mutate({ id: ev.id, status: 'VERIFIED' })}
                        >
                          <BadgeCheck className="h-3.5 w-3.5" />
                          Verify evidence
                        </Button>
                      </div>
                    )}
                  </div>
                ))}

                {fact.status !== 'REJECTED' && (
                  <div className="flex flex-wrap gap-2 border-t border-border pt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateFact.mutate({ id: fact.id, status: 'USER_CONFIRMED' })}
                    >
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Confirm
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateFact.mutate({ id: fact.id, status: 'REJECTED' })}
                      className="text-destructive hover:text-destructive"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}

      {facts.data && facts.data.length === 0 && (
        <section className="card flex flex-col items-center gap-3 p-10 text-center shadow-soft">
          <Sparkles className="h-8 w-8 text-primary" />
          <p className="text-sm text-muted-foreground">
            Your Career Vault is empty. Upload a resume and re-index to start.
          </p>
        </section>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="card p-4 shadow-soft">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      {value === undefined ? (
        <Loader2 className="mt-1 h-5 w-5 animate-spin text-muted-foreground" />
      ) : (
        <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      )}
    </div>
  )
}
