import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FileText, Sparkles, Trash2, Upload } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import { Resume, ResumeVersion } from '../types'
import { Button } from '../components/ui/button'

function parseParsedData(raw: string | null): { designation?: string; skills: string[] } {
  if (!raw) return { skills: [] }
  try {
    const data = JSON.parse(raw)
    const skills = Array.isArray(data.skills) ? data.skills.map(String) : []
    return { designation: data.designation ? String(data.designation) : undefined, skills }
  } catch {
    return { skills: [] }
  }
}

export default function ResumePage() {
  const qc = useQueryClient()
  const { data: resumes } = useQuery({
    queryKey: ['resumes'],
    queryFn: async () => (await api.get('/resumes')).data as Resume[],
  })
  const [uploading, setUploading] = useState(false)
  const [optimized, setOptimized] = useState<Record<number, ResumeVersion>>({})
  const [optimizingId, setOptimizingId] = useState<number | null>(null)

  const upload = useMutation({
    mutationFn: async ({ file, title }: { file: File; title: string }) => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('title', title)
      return (await api.post<Resume>('/resumes/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data
    },
    onSuccess: () => {
      toast.success('Resume uploaded')
      qc.invalidateQueries({ queryKey: ['resumes'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/resumes/${id}`),
    onSuccess: () => {
      toast.success('Resume deleted')
      qc.invalidateQueries({ queryKey: ['resumes'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const optimize = useMutation({
    mutationFn: async ({ resumeId, jobId }: { resumeId: number; jobId: number }) =>
      (
        await api.post<ResumeVersion>(`/resumes/${resumeId}/optimize?job_id=${jobId}`)
      ).data,
    onSuccess: (version, { resumeId }) => {
      setOptimized((prev) => ({ ...prev, [resumeId]: version }))
      toast.success(`Optimized: ${version.version_label ?? 'new version created'}`)
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  async function onUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0]
    const title = (form.elements.namedItem('title') as HTMLInputElement).value
    if (!file) return
    setUploading(true)
    try {
      await upload.mutateAsync({ file, title })
      form.reset()
    } finally {
      setUploading(false)
    }
  }

  function onOptimize(resumeId: number) {
    const raw = window.prompt('Enter the job ID to optimize this resume for:')
    if (!raw) return
    const jobId = Number(raw.trim())
    if (!Number.isFinite(jobId)) return
    setOptimizingId(resumeId)
    optimize.mutate({ resumeId, jobId })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Resumes</h1>

      <form onSubmit={onUpload} className="space-y-4 p-4 border rounded-lg max-w-xl">
        <input name="title" placeholder="Resume title" className="w-full p-2 border rounded bg-background" required />
        <input name="file" type="file" accept=".pdf,.docx" className="w-full p-2 border rounded bg-background" required />
        <Button type="submit" disabled={uploading} className="flex items-center gap-2">
          <Upload className="h-4 w-4" />
          {uploading ? 'Uploading…' : 'Upload Resume'}
        </Button>
      </form>

      <div className="grid gap-4">
        {resumes?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No resumes uploaded yet.</p>}
        {resumes?.map((r) => {
          const version = optimized[r.id]
          return (
            <div key={r.id} className="p-4 border rounded-lg">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <FileText className="h-4 w-4 mt-1 text-muted-foreground" />
                  <div>
                    <h3 className="font-semibold">{r.title}</h3>
                    <p className="text-sm text-muted-foreground">{r.file_type} · {new Date(r.created_at).toLocaleDateString()}</p>
                    {(() => {
                      const { designation, skills } = parseParsedData(r.parsed_data)
                      if (!designation && skills.length === 0) return null
                      return (
                        <div className="mt-2 space-y-1">
                          {designation && (
                            <p className="text-sm">
                              Designation: <span className="font-semibold">{designation}</span>
                            </p>
                          )}
                          {skills.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {skills.map((s) => (
                                <span key={s} className="text-xs bg-muted px-2 py-0.5 rounded">
                                  {s}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })()}
                    {r.ats_score !== null && r.ats_score !== undefined && (
                      <div className="mt-2 space-y-1">
                        <p className="text-sm">
                          ATS Score: <span className="font-semibold">{r.ats_score}</span>
                        </p>
                        {r.missing_keywords && (
                          <p className="text-sm text-amber-600 dark:text-amber-400">
                            Missing keywords: {r.missing_keywords}
                          </p>
                        )}
                        {r.improvement_suggestions && (
                          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{r.improvement_suggestions}</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="outline"
                    onClick={() => onOptimize(r.id)}
                    disabled={optimizingId === r.id || optimize.isPending}
                    className="flex items-center gap-2"
                  >
                    <Sparkles className="h-4 w-4" />
                    {optimizingId === r.id ? 'Optimizing…' : 'Optimize for job'}
                  </Button>
                  <button onClick={() => remove.mutate(r.id)} className="p-2 rounded-md hover:bg-muted" title="Delete resume">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              {version && (
                <details className="mt-3 border rounded-lg">
                  <summary className="cursor-pointer p-3 text-sm font-medium">
                    {version.version_label ?? `Version ${version.id}`}
                  </summary>
                  <pre className="text-xs whitespace-pre-wrap p-3 border-t bg-background">{version.content}</pre>
                </details>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
