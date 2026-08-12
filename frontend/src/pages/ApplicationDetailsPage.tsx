import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Briefcase,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  FileText,
  Download,
  MapPin,
  Tag,
  Trash2,
  Sparkles,
  StickyNote,
  BellRing,
  Globe,
} from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import {
  ApplicationDetail,
  ApplicationNote,
  ApplicationDocument,
  ApplicationReminder,
  ApplicationTimelineEntry,
  ApplicationAuditEntry,
  FollowUpResponse,
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

const ALL_STATUSES = [
  'DRAFT', 'READY', 'APPLIED', 'VIEWED', 'RECRUITER_CONTACT', 'ASSESSMENT',
  'INTERVIEW', 'TECHNICAL_ROUND', 'FINAL_ROUND', 'OFFER', 'REJECTED',
  'WITHDRAWN', 'EXPIRED', 'FAILED',
]

const TABS = ['Overview', 'Timeline', 'Notes', 'Documents', 'Follow-up', 'Reminders'] as const
type Tab = (typeof TABS)[number]

function fmt(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export default function ApplicationDetailsPage() {
  const { id } = useParams()
  const appId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('Overview')

  const { data: app } = useQuery({
    queryKey: ['app', appId],
    queryFn: async () => (await api.get(`/applications/${appId}`)).data as ApplicationDetail,
    enabled: !!appId,
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['app', appId] })
    qc.invalidateQueries({ queryKey: ['apps'] })
    qc.invalidateQueries({ queryKey: ['apps-attention'] })
  }

  const setStatus = useMutation({
    mutationFn: async ({ status, reason }: { status: string; reason?: string }) =>
      (await api.post(`/applications/${appId}/status`, { status, reason })).data,
    onSuccess: () => {
      toast.success('Status updated')
      invalidate()
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const update = useMutation({
    mutationFn: async ({ notes, priority }: { notes?: string; priority?: string }) =>
      (await api.patch(`/applications/${appId}`, { notes, priority })).data,
    onSuccess: () => {
      toast.success('Application updated')
      invalidate()
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const deleteApp = useMutation({
    mutationFn: async () => api.delete(`/applications/${appId}`),
    onSuccess: () => {
      toast.success('Application deleted')
      qc.invalidateQueries({ queryKey: ['apps'] })
      navigate('/applications')
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  // Notes
  const { data: notes } = useQuery({
    queryKey: ['app-notes', appId],
    queryFn: async () => (await api.get(`/applications/${appId}/notes`)).data as ApplicationNote[],
    enabled: !!appId && tab === 'Notes',
  })
  const addNote = useMutation({
    mutationFn: async (note: string) => (await api.post(`/applications/${appId}/notes`, { note })).data,
    onSuccess: () => {
      toast.success('Note added')
      qc.invalidateQueries({ queryKey: ['app-notes', appId] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  // Tags
  const { data: tags } = useQuery({
    queryKey: ['app', appId, 'tags'],
    queryFn: async () => (await api.get(`/applications/${appId}/tags`)).data as string[],
    enabled: !!appId,
  })
  const addTag = useMutation({
    mutationFn: async (tag: string) => (await api.post(`/applications/${appId}/tags`, { tag })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['app', appId] })
      qc.invalidateQueries({ queryKey: ['app', appId, 'tags'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })
  const removeTag = useMutation({
    mutationFn: async (tag: string) => api.delete(`/applications/${appId}/tags/${encodeURIComponent(tag)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['app', appId] })
      qc.invalidateQueries({ queryKey: ['app', appId, 'tags'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  // Timeline + audit
  const { data: timeline } = useQuery({
    queryKey: ['app-timeline', appId],
    queryFn: async () => (await api.get(`/applications/${appId}/timeline`)).data as ApplicationTimelineEntry[],
    enabled: !!appId && tab === 'Timeline',
  })
  const { data: audit } = useQuery({
    queryKey: ['app-audit', appId],
    queryFn: async () => (await api.get(`/applications/${appId}/audit`)).data as ApplicationAuditEntry[],
    enabled: !!appId && tab === 'Timeline',
  })

  // Documents
  const { data: documents } = useQuery({
    queryKey: ['app-docs', appId],
    queryFn: async () => (await api.get(`/applications/${appId}/documents`)).data as ApplicationDocument[],
    enabled: !!appId && tab === 'Documents',
  })

  // Follow-up
  const { data: followup } = useQuery({
    queryKey: ['app-followup', appId],
    queryFn: async () => (await api.post(`/applications/${appId}/follow-up`, { mode: 'professional' })).data as FollowUpResponse,
    enabled: false,
  })
  const generateFollowup = useMutation({
    mutationFn: async () => (await api.post(`/applications/${appId}/follow-up`, { mode: 'professional' })).data as FollowUpResponse,
    onSuccess: (data) => {
      qc.setQueryData(['app-followup', appId], data)
      qc.invalidateQueries({ queryKey: ['app', appId] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  // Reminders
  const { data: reminders } = useQuery({
    queryKey: ['app-reminders', appId],
    queryFn: async () => (await api.get(`/applications/reminders?pending_only=false`)).data as ApplicationReminder[],
    enabled: !!appId && tab === 'Reminders',
  })
  const addReminder = useMutation({
    mutationFn: async ({ reminder_type, due_at }: { reminder_type: string; due_at: string }) =>
      (await api.post(`/applications/${appId}/reminders`, { reminder_type, due_at })).data,
    onSuccess: () => {
      toast.success('Reminder created')
      qc.invalidateQueries({ queryKey: ['app-reminders', appId] })
      qc.invalidateQueries({ queryKey: ['apps-attention'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })
  const completeReminder = useMutation({
    mutationFn: async (reminderId: number) =>
      (await api.post(`/applications/reminders/${reminderId}/complete`)).data,
    onSuccess: () => {
      toast.success('Reminder completed')
      qc.invalidateQueries({ queryKey: ['app-reminders', appId] })
      qc.invalidateQueries({ queryKey: ['apps-attention'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const [noteText, setNoteText] = useState('')
  const [tagText, setTagText] = useState('')
  const [notesEdit, setNotesEdit] = useState('')
  const [priority, setPriority] = useState('MEDIUM')
  const [reminderType, setReminderType] = useState('FOLLOW_UP')
  const [reminderDue, setReminderDue] = useState('')

  if (!app) {
    return (
      <div className="space-y-4">
        <Link to="/applications" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to applications
        </Link>
        <p className="text-sm text-muted-foreground p-4 border rounded-lg">Loading application...</p>
      </div>
    )
  }

  const snapshot = app.snapshot

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <Link to="/applications" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to applications
        </Link>
        <Button variant="destructive" size="sm" className="flex items-center gap-2" onClick={() => deleteApp.mutate()}>
          <Trash2 className="h-4 w-4" /> Delete
        </Button>
      </div>

      <div className="p-6 border rounded-lg bg-card/60 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold">{app.job_title ?? `Application #${app.id}`}</h1>
              <span className={cn('inline-block text-xs uppercase px-2 py-0.5 rounded', STATUS_STYLES[app.status] ?? 'bg-muted')}>
                {app.status.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2 flex-wrap">
              {app.company_name && <span className="inline-flex items-center gap-1"><Briefcase className="h-3 w-3" />{app.company_name}</span>}
              {snapshot?.location && <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{snapshot.location}</span>}
              {snapshot?.country && <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />{snapshot.country}</span>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={app.status}
              onChange={(e) => setStatus.mutate({ status: e.target.value })}
              className="h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {ALL_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              disabled={!app.applied_at}
              onClick={() => {
                const next =
                  app.status === 'APPLIED' ? 'INTERVIEW' : app.status === 'INTERVIEW' ? 'TECHNICAL_ROUND' : app.status === 'TECHNICAL_ROUND' ? 'FINAL_ROUND' : 'APPLIED'
                if (next !== app.status) setStatus.mutate({ status: next })
              }}
            >
              Advance
            </Button>
          </div>
        </div>

        {app.match_score != null && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Match score</span>
            <div className="h-2 flex-1 max-w-xs rounded-full bg-muted overflow-hidden">
              <div className="h-full bg-gradient-to-r from-primary to-violet-500 rounded-full" style={{ width: `${app.match_score}%` }} />
            </div>
            <span className="text-sm font-semibold">{app.match_score}%</span>
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Source</p>
            <p className="font-medium">{app.application_source.replace(/_/g, ' ')}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Priority</p>
            <p className="font-medium">{app.priority}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Applied</p>
            <p className="font-medium">{fmt(app.applied_at)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Responded</p>
            <p className="font-medium">{fmt(app.responded_at)}</p>
          </div>
        </div>

        {tags && tags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            {tags.map((t) => (
              <span key={t} className="inline-flex items-center gap-1 text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                <Tag className="h-3 w-3" /> {t}
                <button onClick={() => removeTag.mutate(t)} className="hover:text-destructive">×</button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-1 border-b border-border flex-wrap">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              tab === t ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="p-4 border rounded-lg space-y-3">
              <h2 className="font-semibold flex items-center gap-2">
                <StickyNote className="h-4 w-4 text-muted-foreground" /> Notes & priority
              </h2>
              <textarea
                defaultValue={app.notes ?? ''}
                onChange={(e) => setNotesEdit(e.target.value)}
                placeholder="Add private notes about this application..."
                rows={4}
                className="w-full rounded-md border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <div className="flex items-center gap-2">
                <select value={priority} onChange={(e) => setPriority(e.target.value)} className="h-9 rounded-md border border-border bg-background px-3 text-sm">
                  <option value="HIGH">High</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="LOW">Low</option>
                </select>
                <Button
                  size="sm"
                  onClick={() => update.mutate({ notes: notesEdit, priority })}
                >
                  Save
                </Button>
              </div>
            </div>

            <div className="p-4 border rounded-lg space-y-3">
              <h2 className="font-semibold flex items-center gap-2">
                <Tag className="h-4 w-4 text-muted-foreground" /> Add tag
              </h2>
              <div className="flex items-center gap-2">
                <input
                  value={tagText}
                  onChange={(e) => setTagText(e.target.value)}
                  placeholder="e.g. remote, referral, dream-company"
                  className="flex-1 h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                <Button
                  size="sm"
                  onClick={() => {
                    if (tagText.trim()) {
                      addTag.mutate(tagText.trim())
                      setTagText('')
                    }
                  }}
                >
                  Add
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-4 border rounded-lg">
              <h2 className="font-semibold mb-2">Job snapshot (frozen at application time)</h2>
              {snapshot ? (
                <div className="space-y-2 text-sm text-muted-foreground">
                  <div className="flex items-center gap-3 flex-wrap">
                    {snapshot.salary_min != null && (
                      <span>
                        {snapshot.salary_currency ?? ''} {snapshot.salary_min.toLocaleString()}
                        {snapshot.salary_max ? ` – ${snapshot.salary_max.toLocaleString()}` : ''}
                      </span>
                    )}
                    {snapshot.remote_type && <span>{snapshot.remote_type}</span>}
                    {snapshot.job_quality_score != null && <span>Quality {snapshot.job_quality_score}/100</span>}
                  </div>
                  {snapshot.description && <p className="line-clamp-4">{snapshot.description}</p>}
                  {snapshot.source_url && (
                    <a href={snapshot.source_url} target="_blank" rel="noreferrer" className="text-primary hover:underline block">
                      View original job listing
                    </a>
                  )}
                  {snapshot.requirements && (
                    <div>
                      <p className="font-medium text-foreground mt-2 mb-1">Requirements</p>
                      <p className="whitespace-pre-line">{snapshot.requirements}</p>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No snapshot captured.</p>
              )}
            </div>

            <div className="p-4 border rounded-lg">
              <h2 className="font-semibold mb-2">Follow-up status</h2>
              {app.follow_up_status ? (
                <div className="space-y-1 text-sm">
                  <p className="text-muted-foreground">{app.follow_up_reason ?? '—'}</p>
                  {app.follow_up_recommended_at && (
                    <p className="text-xs text-muted-foreground">Checked {fmt(app.follow_up_recommended_at)}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Run the Follow-up tab to get a recommendation.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'Timeline' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-3">
            <h2 className="font-semibold flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-muted-foreground" /> Status history
            </h2>
            {timeline?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No status changes recorded yet.</p>}
            {timeline?.map((t, i) => (
              <div key={i} className="flex items-start gap-3 p-3 border rounded-lg">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">{t.old_status?.replace(/_/g, ' ') ?? '—'}</span>
                  <span>→</span>
                  <span className="font-semibold">{t.new_status?.replace(/_/g, ' ') ?? '—'}</span>
                </div>
                <div className="ml-auto text-right">
                  <p className="text-xs text-muted-foreground">{fmt(t.changed_at)}</p>
                  {t.reason && <p className="text-xs text-muted-foreground">{t.reason}</p>}
                </div>
              </div>
            ))}
          </div>
          <div className="space-y-3">
            <h2 className="font-semibold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-muted-foreground" /> Audit log
            </h2>
            {audit?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No audit events yet.</p>}
            {audit?.map((a, i) => (
              <div key={i} className="p-3 border rounded-lg text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{a.event}</span>
                  <span className="text-xs text-muted-foreground">{fmt(a.timestamp)}</span>
                </div>
                {a.metadata && Object.keys(a.metadata).length > 0 && (
                  <pre className="mt-1 text-xs text-muted-foreground whitespace-pre-wrap">{JSON.stringify(a.metadata, null, 2)}</pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'Notes' && (
        <div className="space-y-3 max-w-2xl">
          <div className="flex items-center gap-2">
            <input
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Write a note..."
              className="flex-1 h-9 rounded-md border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <Button
              onClick={() => {
                if (noteText.trim()) {
                  addNote.mutate(noteText.trim())
                  setNoteText('')
                }
              }}
            >
              Add note
            </Button>
          </div>
          {notes?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No notes yet.</p>}
          {notes?.map((n) => (
            <div key={n.id} className="p-4 border rounded-lg flex items-start justify-between gap-3">
              <p className="text-sm">{n.note}</p>
              <span className="text-xs text-muted-foreground shrink-0">{fmt(n.created_at)}</span>
            </div>
          ))}
        </div>
      )}

      {tab === 'Documents' && (
        <div className="space-y-3 max-w-2xl">
          {documents?.length === 0 && (
            <p className="text-sm text-muted-foreground p-4 border rounded-lg">
              No documents frozen for this application. They are captured when the application is created.
            </p>
          )}
          {documents?.map((d) => (
            <div key={d.id} className="p-4 border rounded-lg flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{d.doc_type.replace(/_/g, ' ')}</p>
                  {d.version_label && <p className="text-xs text-muted-foreground">{d.version_label}</p>}
                </div>
              </div>
              <a
                href={`${import.meta.env.VITE_API_URL || 'http://localhost:8001'}${d.download_url}`}
                className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
              >
                <Download className="h-4 w-4" /> Download
              </a>
            </div>
          ))}
        </div>
      )}

      {tab === 'Follow-up' && (
        <div className="space-y-4 max-w-2xl">
          <div className="p-4 border rounded-lg">
            <h2 className="font-semibold flex items-center gap-2 mb-2">
              <BellRing className="h-4 w-4 text-muted-foreground" /> Follow-up assistant
            </h2>
            <p className="text-sm text-muted-foreground mb-3">
              Never send before a full week has passed. This only recommends and drafts a message — it never sends anything.
            </p>
            <Button onClick={() => generateFollowup.mutate()} disabled={generateFollowup.isPending}>
              Generate follow-up message
            </Button>
          </div>

          {(followup || generateFollowup.data) && (
            <div className="p-4 border rounded-lg space-y-3">
              {followup?.recommended ? (
                <p className="flex items-center gap-2 text-sm font-medium text-green-600 dark:text-green-400">
                  <CheckCircle2 className="h-4 w-4" /> Recommended: {followup.reason}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">{followup?.reason ?? 'Recommendation not available.'}</p>
              )}
              {followup?.message && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Draft message</h3>
                  <p className="text-sm whitespace-pre-line p-3 rounded-md bg-muted">{followup.message}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'Reminders' && (
        <div className="space-y-4 max-w-2xl">
          <div className="p-4 border rounded-lg space-y-3">
            <h2 className="font-semibold flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-muted-foreground" /> New reminder
            </h2>
            <div className="flex items-center gap-2 flex-wrap">
              <select value={reminderType} onChange={(e) => setReminderType(e.target.value)} className="h-9 rounded-md border border-border bg-background px-3 text-sm">
                <option value="FOLLOW_UP">Follow up</option>
                <option value="INTERVIEW">Interview</option>
                <option value="ASSESSMENT_DEADLINE">Assessment deadline</option>
                <option value="RECRUITER_RESPONSE">Recruiter response</option>
              </select>
              <input
                type="datetime-local"
                value={reminderDue}
                onChange={(e) => setReminderDue(e.target.value)}
                className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              />
              <Button
                onClick={() => {
                  if (reminderDue) {
                    addReminder.mutate({ reminder_type: reminderType, due_at: new Date(reminderDue).toISOString() })
                    setReminderDue('')
                  }
                }}
              >
                Create
              </Button>
            </div>
          </div>

          {reminders?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No reminders yet.</p>}
          {reminders?.map((r) => (
            <div key={r.id} className="p-4 border rounded-lg flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{r.reminder_type.replace(/_/g, ' ')}</p>
                <p className="text-xs text-muted-foreground">Due {fmt(r.due_at)} · {r.status}</p>
              </div>
              {r.status === 'PENDING' && (
                <Button variant="outline" size="sm" onClick={() => completeReminder.mutate(r.id)}>
                  Mark complete
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
