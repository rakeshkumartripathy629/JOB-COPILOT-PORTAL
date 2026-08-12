import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Briefcase,
  Download,
  FileText,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Inbox,
  Search,
  CalendarClock,
  ChevronRight,
} from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import {
  Application,
  ApplicationAnalytics,
  NeedsAttentionItem,
} from '../types'
import { Button } from '../components/ui/button'
import { cn } from '../utils/cn'

const STATUS_STYLES: Record<string, string> = {
  DRAFT: 'bg-muted text-muted-foreground',
  READY: 'bg-sky-500/10 text-sky-700 dark:text-sky-400',
  APPLIED: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  VIEWED: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-400',
  RECRUITER_CONTACT: 'bg-teal-500/10 text-teal-700 dark:text-teal-400',
  ASSESSMENT: 'bg-purple-500/10 text-purple-700 dark:text-purple-400',
  INTERVIEW: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  TECHNICAL_ROUND: 'bg-orange-500/10 text-orange-700 dark:text-orange-400',
  FINAL_ROUND: 'bg-pink-500/10 text-pink-700 dark:text-pink-400',
  OFFER: 'bg-green-500/10 text-green-700 dark:text-green-400',
  REJECTED: 'bg-red-500/10 text-red-700 dark:text-red-400',
  WITHDRAWN: 'bg-slate-500/10 text-slate-700 dark:text-slate-400',
  EXPIRED: 'bg-slate-500/10 text-slate-700 dark:text-slate-400',
  FAILED: 'bg-red-500/10 text-red-700 dark:text-red-400',
  UNKNOWN: 'bg-muted text-muted-foreground',
}

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'match_score', label: 'Best match' },
  { value: 'priority', label: 'Priority' },
  { value: 'company', label: 'Company' },
  { value: 'status', label: 'Status' },
]

const NEXT_STATUS: Record<string, string> = {
  DRAFT: 'READY',
  READY: 'APPLIED',
  APPLIED: 'INTERVIEW',
  INTERVIEW: 'TECHNICAL_ROUND',
  TECHNICAL_ROUND: 'FINAL_ROUND',
  FINAL_ROUND: 'OFFER',
}

export default function ApplicationsPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('newest')

  const { data: apps } = useQuery({
    queryKey: ['apps', status, search, sort],
    queryFn: async () => {
      const params = new URLSearchParams({ sort })
      if (status) params.set('status', status)
      if (search) params.set('search', search)
      return (await api.get(`/applications?${params.toString()}`)).data as Application[]
    },
  })

  const { data: analytics } = useQuery({
    queryKey: ['apps-analytics'],
    queryFn: async () => (await api.get('/applications/analytics')).data as ApplicationAnalytics,
  })

  const { data: attention } = useQuery({
    queryKey: ['apps-attention'],
    queryFn: async () => (await api.get('/applications/needs-attention')).data as NeedsAttentionItem[],
  })

  const advance = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) =>
      (await api.post<Application>(`/applications/${id}/status`, { status })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['apps'] })
      qc.invalidateQueries({ queryKey: ['apps-analytics'] })
      qc.invalidateQueries({ queryKey: ['apps-attention'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/applications/${id}`),
    onSuccess: () => {
      toast.success('Application removed')
      qc.invalidateQueries({ queryKey: ['apps'] })
      qc.invalidateQueries({ queryKey: ['apps-analytics'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const stats = useMemo(
    () => [
      { label: 'Total', value: analytics?.total_applications ?? 0, icon: Inbox },
      { label: 'Applied', value: analytics?.applied ?? 0, icon: Briefcase },
      { label: 'Interviews', value: analytics?.interviews ?? 0, icon: CalendarClock },
      { label: 'Offers', value: analytics?.offers ?? 0, icon: CheckCircle2 },
      { label: 'Rejected', value: analytics?.rejected ?? 0, icon: XCircle },
      { label: 'Response rate', value: `${analytics?.response_rate ?? 0}%`, icon: FileText },
    ],
    [analytics],
  )

  const openStatuses = ['DRAFT', 'READY', 'APPLIED', 'VIEWED', 'RECRUITER_CONTACT', 'ASSESSMENT', 'INTERVIEW', 'TECHNICAL_ROUND', 'FINAL_ROUND']

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold">Applications</h1>
          <p className="text-sm text-muted-foreground mt-1">Track every application from draft to offer.</p>
        </div>
        <div className="flex items-center gap-2">
          <a href={`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}/applications/export.csv`}>
            <Button variant="outline" className="flex items-center gap-2">
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((s) => (
          <div key={s.label} className="p-4 border rounded-lg bg-card/60">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">{s.label}</span>
              <s.icon className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="text-2xl font-bold mt-2">{s.value}</p>
          </div>
        ))}
      </div>

      {attention && attention.length > 0 && (
        <div className="border border-amber-500/30 bg-amber-500/5 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <h2 className="font-semibold text-sm">Needs attention ({attention.length})</h2>
          </div>
          <div className="space-y-2">
            {attention.map((a, i) => (
              <Link
                key={i}
                to={`/applications/${a.application_id}`}
                className="flex items-center justify-between gap-3 text-sm text-amber-700 dark:text-amber-400 hover:underline"
              >
                <span>
                  {a.job_title} — {a.company_name}: {a.reason}
                </span>
                <ChevronRight className="h-4 w-4 shrink-0" />
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search jobs, companies..."
            className="w-full h-9 rounded-md border border-border bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All statuses</option>
          {openStatuses.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-3">
        {apps?.length === 0 && (
          <p className="text-sm text-muted-foreground p-4 border rounded-lg">
            No applications found. Save jobs from the Jobs page or use the Jobs page to create an application.
          </p>
        )}
        {apps?.map((a) => {
          const next = NEXT_STATUS[a.status]
          return (
            <div key={a.id} className="p-4 border rounded-lg flex items-center justify-between gap-4 hover:border-primary/30 transition-colors">
              <Link to={`/applications/${a.id}`} className="flex items-start gap-3 flex-1 min-w-0">
                <Briefcase className="h-4 w-4 mt-1 text-muted-foreground shrink-0" />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold truncate">{a.job_title ?? `Application #${a.id}`}</h3>
                    {a.match_score != null && (
                      <span className="text-[10px] uppercase bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                        match {a.match_score}%
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground truncate">{a.company_name}</p>
                  {a.notes && <p className="text-sm text-muted-foreground mt-1 line-clamp-1">{a.notes}</p>}
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span className={cn('inline-block text-[10px] uppercase px-2 py-0.5 rounded', STATUS_STYLES[a.status] ?? 'bg-muted')}>
                      {a.status.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{a.priority}</span>
                    {a.applied_at && (
                      <span className="text-xs text-muted-foreground">Applied {new Date(a.applied_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              </Link>
              <div className="flex items-center gap-2 shrink-0">
                {next && a.status !== 'OFFER' && a.status !== 'REJECTED' && a.status !== 'WITHDRAWN' && (
                  <Button variant="outline" size="sm" onClick={() => advance.mutate({ id: a.id, status: next })}>
                    Mark {next.replace(/_/g, ' ')}
                  </Button>
                )}
                <button onClick={() => remove.mutate(a.id)} className="p-2 rounded-md hover:bg-muted" title="Remove">
                  <XCircle className="h-4 w-4" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
