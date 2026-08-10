import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Briefcase, Trash2 } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import { Application } from '../types'
import { Button } from '../components/ui/button'
import { cn } from '../utils/cn'

const STATUS_STYLES: Record<string, string> = {
  saved: 'bg-muted text-muted-foreground',
  pending: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  oa: 'bg-purple-500/10 text-purple-700 dark:text-purple-400',
  interview: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  offer: 'bg-green-500/10 text-green-700 dark:text-green-400',
  rejected: 'bg-red-500/10 text-red-700 dark:text-red-400',
}

const NEXT_STATUS: Record<string, string> = {
  saved: 'pending',
  pending: 'oa',
  oa: 'interview',
  interview: 'offer',
  offer: 'offer',
  rejected: 'rejected',
}

export default function ApplicationsPage() {
  const qc = useQueryClient()
  const { data: apps } = useQuery({
    queryKey: ['apps'],
    queryFn: async () => (await api.get('/applications')).data as Application[],
  })

  const advance = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) =>
      (await api.patch<Application>(`/applications/${id}`, { status })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['apps'] })
      qc.invalidateQueries({ queryKey: ['analytics'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/applications/${id}`),
    onSuccess: () => {
      toast.success('Application removed')
      qc.invalidateQueries({ queryKey: ['apps'] })
      qc.invalidateQueries({ queryKey: ['analytics'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Applications</h1>
      <div className="grid gap-4">
        {apps?.length === 0 && (
          <p className="text-sm text-muted-foreground p-4 border rounded-lg">No applications yet. Save jobs from the Jobs page.</p>
        )}
        {apps?.map((a) => {
          const next = NEXT_STATUS[a.status]
          return (
            <div key={a.id} className="p-4 border rounded-lg flex items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <Briefcase className="h-4 w-4 mt-1 text-muted-foreground" />
                <div>
                  <h3 className="font-semibold">{a.job_title}</h3>
                  <p className="text-sm text-muted-foreground">{a.company_name}</p>
                  {a.notes && <p className="text-sm text-muted-foreground mt-1">{a.notes}</p>}
                  <span className={cn('inline-block mt-2 text-xs uppercase px-2 py-1 rounded', STATUS_STYLES[a.status] ?? 'bg-muted')}>
                    {a.status}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {next !== a.status && (
                  <Button variant="outline" onClick={() => advance.mutate({ id: a.id, status: next })}>
                    Mark {next}
                  </Button>
                )}
                <button onClick={() => remove.mutate(a.id)} className="p-2 rounded-md hover:bg-muted" title="Remove">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
