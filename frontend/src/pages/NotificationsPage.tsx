import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Bell, CheckCheck, Trash2 } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import { Notification } from '../types'
import { Button } from '../components/ui/button'

export default function NotificationsPage() {
  const qc = useQueryClient()
  const { data: notifs } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => (await api.get('/notifications')).data as Notification[],
  })

  const markOne = useMutation({
    mutationFn: async (id: number) => api.patch(`/notifications/${id}/read`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notif-unread'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const markAll = useMutation({
    mutationFn: async () => api.post('/notifications/read-all'),
    onSuccess: () => {
      toast.success('All notifications marked as read')
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notif-unread'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/notifications/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notif-unread'] })
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const unread = notifs?.filter((n) => !n.is_read).length ?? 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Notifications</h1>
        <Button
          variant="outline"
          onClick={() => markAll.mutate()}
          disabled={unread === 0 || markAll.isPending}
          className="flex items-center gap-2"
        >
          <CheckCheck className="h-4 w-4" />
          Mark all read
        </Button>
      </div>
      <div className="space-y-3">
        {notifs?.length === 0 && (
          <p className="text-sm text-muted-foreground p-4 border rounded-lg">No notifications yet.</p>
        )}
        {notifs?.map((n) => (
          <div
            key={n.id}
            className={`p-4 border rounded-lg flex items-start justify-between gap-4 ${n.is_read ? '' : 'bg-primary/5 border-primary/20'}`}
          >
            <button
              className="flex items-start gap-3 text-left flex-1"
              onClick={() => !n.is_read && markOne.mutate(n.id)}
              disabled={n.is_read}
            >
              <Bell className={`h-4 w-4 mt-1 ${n.is_read ? 'text-muted-foreground' : 'text-primary'}`} />
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-sm">{n.title}</h3>
                  {!n.is_read && <span className="text-[10px] uppercase bg-primary text-primary-foreground px-1.5 py-0.5 rounded">new</span>}
                </div>
                {n.message && <p className="text-sm text-muted-foreground mt-1">{n.message}</p>}
                <p className="text-xs text-muted-foreground mt-1">{new Date(n.created_at).toLocaleString()}</p>
              </div>
            </button>
            <button onClick={() => remove.mutate(n.id)} className="p-2 rounded-md hover:bg-muted shrink-0" title="Delete notification">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
