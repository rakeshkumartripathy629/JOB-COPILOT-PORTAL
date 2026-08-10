import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { InterviewEvaluation, InterviewQuestion, Job } from '../types'
import { Button } from '../components/ui/button'
import { CheckCircle2, ChevronDown, MessageSquare, Plus, Trash2 } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'

const CATEGORIES = ['technical', 'behavioral', 'system_design', 'hr']

export default function InterviewPrepPage() {
  const qc = useQueryClient()
  const [jobId, setJobId] = useState<number | ''>('')
  const [categories, setCategories] = useState<string[]>([])

  const { data: allJobs } = useQuery({
    queryKey: ['all-jobs'],
    queryFn: async () => (await api.get('/jobs/search?limit=50')).data as Job[],
  })

  const { data: questions } = useQuery({
    queryKey: ['interview-questions'],
    queryFn: async () => (await api.get('/interviews/questions')).data as InterviewQuestion[],
  })

  const jobs = useMemo(() => {
    const map = new Map<number, Job>()
    allJobs?.forEach((j) => {
      if (!map.has(j.id)) map.set(j.id, j)
    })
    return Array.from(map.values())
  }, [allJobs])

  const grouped = useMemo(() => {
    const map = new Map<number, InterviewQuestion[]>()
    questions?.forEach((q) => {
      const list = map.get(q.job_id) ?? []
      list.push(q)
      map.set(q.job_id, list)
    })
    return Array.from(map.entries())
  }, [questions])

  const generate = useMutation({
    mutationFn: async () =>
      (
        await api.post<InterviewQuestion[]>('/interviews/questions', {
          job_id: Number(jobId),
          categories,
        })
      ).data,
    onSuccess: (created) => {
      toast.success(created.length ? `Generated ${created.length} questions` : 'Questions generated')
      qc.invalidateQueries({ queryKey: ['interview-questions'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/interviews/questions/${id}`),
    onSuccess: () => {
      toast.success('Question deleted')
      qc.invalidateQueries({ queryKey: ['interview-questions'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  function toggleCategory(cat: string) {
    setCategories((prev) => (prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]))
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Interview Prep</h1>

      <div className="p-4 border rounded-lg space-y-4 max-w-xl">
        <label className="block">
          <span className="text-sm font-medium">Job</span>
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : '')}
            className="w-full mt-1 p-2 border rounded bg-background"
          >
            <option value="">Select a job…</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} {j.company_name ? `– ${j.company_name}` : ''}
              </option>
            ))}
          </select>
          {jobs.length === 0 && (
            <p className="text-xs text-muted-foreground mt-1">No jobs available yet.</p>
          )}
        </label>

        <div>
          <span className="text-sm font-medium">Categories</span>
          <div className="flex flex-wrap gap-2 mt-1">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => toggleCategory(c)}
                className={`px-3 py-1 text-xs rounded-full border ${categories.includes(c) ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}
              >
                {c.replace('_', ' ')}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Leave empty to let the AI pick categories from the job description.</p>
        </div>

        <Button
          disabled={jobId === '' || generate.isPending}
          onClick={() => generate.mutate()}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          {generate.isPending ? 'Generating…' : 'Generate Questions'}
        </Button>
      </div>

      {grouped.length === 0 && (
        <p className="text-sm text-muted-foreground p-4 border rounded-lg">
          No questions yet. Pick a job and generate questions to practice.
        </p>
      )}

      {grouped.map(([job, qs]) => (
        <section key={job} className="space-y-3">
          <h2 className="text-lg font-semibold">Job #{job}</h2>
          {qs.map((q) => (
            <QuestionCard key={q.id} q={q} onDelete={() => remove.mutate(q.id)} />
          ))}
        </section>
      ))}
    </div>
  )
}

function QuestionCard({ q, onDelete }: { q: InterviewQuestion; onDelete: () => void }) {
  const [open, setOpen] = useState(false)
  const [answer, setAnswer] = useState('')

  const evaluate = useMutation({
    mutationFn: async () =>
      (await api.post<InterviewEvaluation>(`/interviews/questions/${q.id}/evaluate`, { answer })).data,
    onSuccess: () => toast.success('Answer evaluated'),
    onError: (err) => toast.error(getApiError(err)),
  })

  return (
    <div className="p-4 border rounded-lg space-y-2">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <MessageSquare className="h-4 w-4 mt-1 shrink-0 text-muted-foreground" />
          <div>
            <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded bg-muted">{q.category}</span>
            <p className="font-medium mt-1">{q.question}</p>
          </div>
        </div>
        <button onClick={onDelete} className="p-2 rounded-md hover:bg-muted shrink-0" title="Delete question">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      {q.suggested_answer && (
        <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
          {open ? 'Hide suggested answer' : 'Show suggested answer'}
        </button>
      )}
      {open && q.suggested_answer && (
        <p className="text-sm text-muted-foreground whitespace-pre-wrap border-t pt-2">{q.suggested_answer}</p>
      )}

      <div className="border-t pt-2 space-y-2">
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={4}
          placeholder="Type your answer, then get AI feedback…"
          className="w-full p-2 border rounded bg-background text-sm"
        />
        <Button
          variant="outline"
          disabled={answer.trim().length < 5 || evaluate.isPending}
          onClick={() => evaluate.mutate()}
          className="flex items-center gap-2 px-3 py-1 text-sm"
        >
          <CheckCircle2 className="h-4 w-4" />
          {evaluate.isPending ? 'Evaluating…' : 'Evaluate answer'}
        </Button>
        {evaluate.data && (
          <div className="space-y-2 text-sm border rounded p-3 bg-muted/40">
            <p className="font-semibold">
              Score: <span className="text-primary">{evaluate.data.score}/100</span>
            </p>
            <p>
              <span className="font-medium">Strengths:</span> {evaluate.data.strengths}
            </p>
            <p>
              <span className="font-medium">Improve:</span> {evaluate.data.improvements}
            </p>
            {evaluate.data.model_answer && (
              <p className="text-muted-foreground whitespace-pre-wrap border-t pt-2">
                <span className="font-medium text-foreground">Model answer:</span> {evaluate.data.model_answer}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
