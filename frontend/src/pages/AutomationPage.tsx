import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Bot, Check, Loader2, X } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import { Application, AutomationSession } from '../types'
import { Button } from '../components/ui/button'

const ACTIVE: AutomationSession['status'][] = ['started', 'running']

type Step = { step: string; status: string; detail?: string }
type AutomationResult = {
  url: string
  summary: string
  filled: { name: string; value: string }[]
  notes: string[]
}

function parseSteps(raw?: string | null): Step[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function parseResult(raw?: string | null): AutomationResult | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as AutomationResult
  } catch {
    return null
  }
}

export default function AutomationPage() {
  const [jobId, setJobId] = useState('')
  const [url, setUrl] = useState('')
  const [session, setSession] = useState<AutomationSession | null>(null)
  const [autoAnalyzed, setAutoAnalyzed] = useState(false)

  const { data: apps } = useQuery({
    queryKey: ['apps'],
    queryFn: async () => (await api.get('/applications')).data as Application[],
  })

  const start = useMutation({
    mutationFn: async () =>
      (
        await api.post<AutomationSession>('/automation/start', {
          job_id: Number(jobId),
          job_url: url,
        })
      ).data,
    onSuccess: async (s) => {
      setSession(s)
      setAutoAnalyzed(false)
      toast.success('Automation session started — analyzing the job page…')
      try {
        const { data } = await api.post<AutomationSession>(`/automation/${s.id}/analyze`)
        setSession(data)
        setAutoAnalyzed(true)
        toast.success('Job page analyzed — review the filled draft')
      } catch (err) {
        toast.error(getApiError(err))
      }
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const confirm = useMutation({
    mutationFn: async () =>
      (
        await api.post<AutomationSession>(`/automation/${session?.id}/confirm`, {
          confirmed: true,
        })
      ).data,
    onSuccess: (s) => {
      setSession(s)
      toast.success('Draft confirmed')
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const cancel = useMutation({
    mutationFn: async () =>
      (await api.post<AutomationSession>(`/automation/${session?.id}/cancel`)).data,
    onSuccess: (s) => {
      setSession(s)
      toast.info('Automation cancelled')
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  useEffect(() => {
    const id = session?.id
    const status = session?.status
    if (!id || !status || !ACTIVE.includes(status)) return
    const t = setInterval(async () => {
      try {
        const { data } = await api.get<AutomationSession>(`/automation/${id}`)
        setSession(data)
      } catch {
        // keep last known state
      }
    }, 3000)
    return () => clearInterval(t)
  }, [session?.id, session?.status])

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!jobId || !url.trim()) return
    start.mutate()
  }

  const steps = parseSteps(session?.steps)
  const result = parseResult(session?.result)
  const terminal = session && !ACTIVE.includes(session.status)

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Automation</h1>

      <form onSubmit={onSubmit} className="space-y-4 p-4 border rounded-lg max-w-lg">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Job (from saved applications)</span>
          <select value={jobId} onChange={(e) => setJobId(e.target.value)} className="w-full p-2 border rounded bg-background" required>
            <option value="">Select a job…</option>
            {apps?.map((a) => (
              <option key={a.id} value={a.job_id}>
                {a.job_title ?? `Job #${a.job_id}`} — {a.company_name ?? 'Unknown'}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Job application URL</span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://careers.company.com/jobs/123/apply"
            className="w-full p-2 border rounded bg-background"
            required
          />
        </label>
        <Button type="submit" disabled={start.isPending} className="flex items-center gap-2">
          <Bot className="h-4 w-4" />
          {start.isPending ? 'Starting…' : 'Start Automation'}
        </Button>
      </form>

      {session && (
        <div className="p-4 border rounded-lg max-w-2xl space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Session #{session.id}</h2>
            <span className="text-xs uppercase tracking-wide px-2 py-1 rounded bg-primary/10">
              {session.status}
            </span>
          </div>
          <p className="text-sm text-muted-foreground break-all">{session.job_url}</p>

          {steps.length > 0 && (
            <ol className="space-y-1 text-sm">
              {steps.map((step, i) => (
                <li key={i} className="flex items-center gap-2">
                  {step.status === 'done' ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : step.status === 'failed' ? (
                    <X className="h-4 w-4 text-red-500" />
                  ) : (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  <span>{step.detail ?? step.step}</span>
                </li>
              ))}
            </ol>
          )}

          {result && (
            <div className="space-y-3 border-t pt-3">
              <p className="text-sm">{result.summary}</p>
              {result.filled.length > 0 ? (
                <div className="rounded border overflow-hidden">
                  <div className="text-xs uppercase tracking-wide px-3 py-2 bg-primary/10 font-medium">Filled draft</div>
                  <table className="w-full text-sm">
                    <tbody>
                      {result.filled.map((f) => (
                        <tr key={f.name} className="border-t">
                          <td className="px-3 py-2 text-muted-foreground align-top w-2/5">{f.name}</td>
                          <td className="px-3 py-2 break-all">{f.value || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No fields could be filled from your profile. The job page may use a third-party application system.
                </p>
              )}
              {result.notes.length > 0 && (
                <div className="text-sm text-muted-foreground">
                  <p className="font-medium">Notes</p>
                  <ul className="list-disc pl-5 space-y-1">
                    {result.notes.map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {session.status === 'running' && !result && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing job page…
            </div>
          )}

          {terminal && (
            <p className="text-sm text-muted-foreground">
              {session.user_confirmed ? 'Confirmed.' : session.status === 'cancelled' ? 'Cancelled.' : 'Closed.'}
            </p>
          )}

          {session.status === 'running' && autoAnalyzed && session.confirmation_required && (
            <div className="flex gap-2">
              <Button onClick={() => confirm.mutate()} disabled={confirm.isPending} className="flex items-center gap-2">
                <Check className="h-4 w-4" />
                Confirm
              </Button>
              <Button variant="outline" onClick={() => cancel.mutate()} disabled={cancel.isPending} className="flex items-center gap-2">
                <X className="h-4 w-4" />
                Cancel
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
