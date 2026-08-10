import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { History, ScrollText, Users } from 'lucide-react'
import api from '../services/api'
import { ActivityLog, AdminUser, AiLog } from '../types'
import { Button } from '../components/ui/button'

type Tab = 'users' | 'ai-logs' | 'activity-logs'

const TABS: { id: Tab; label: string; icon: typeof Users }[] = [
  { id: 'users', label: 'Users', icon: Users },
  { id: 'ai-logs', label: 'AI Logs', icon: ScrollText },
  { id: 'activity-logs', label: 'Activity Logs', icon: History },
]

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>('users')

  const users = useQuery({
    queryKey: ['admin-users'],
    queryFn: async (): Promise<AdminUser[]> => (await api.get('/admin/users')).data,
    enabled: tab === 'users',
  })

  const aiLogs = useQuery({
    queryKey: ['admin-ai-logs'],
    queryFn: async (): Promise<AiLog[]> => (await api.get('/admin/ai-logs')).data,
    enabled: tab === 'ai-logs',
  })

  const activityLogs = useQuery({
    queryKey: ['admin-activity-logs'],
    queryFn: async (): Promise<ActivityLog[]> => (await api.get('/admin/activity-logs')).data,
    enabled: tab === 'activity-logs',
  })

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Admin</h1>

      <div className="flex gap-2">
        {TABS.map((t) => (
          <Button key={t.id} variant={tab === t.id ? 'default' : 'outline'} onClick={() => setTab(t.id)} className="flex items-center gap-2">
            <t.icon className="h-4 w-4" />
            {t.label}
          </Button>
        ))}
      </div>

      {tab === 'users' && (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="text-left p-3">ID</th>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Email</th>
                <th className="text-left p-3">Active</th>
              </tr>
            </thead>
            <tbody>
              {users.data?.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="p-3">{u.id}</td>
                  <td className="p-3">{u.full_name}</td>
                  <td className="p-3">{u.email}</td>
                  <td className="p-3">{u.is_active ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'ai-logs' && (
        <div className="space-y-2">
          {aiLogs.data?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No AI logs yet.</p>}
          {aiLogs.data?.map((log) => (
            <div key={log.id} className="p-3 border rounded-lg flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{log.agent_type}</p>
                <p className="text-xs text-muted-foreground">User #{log.user_id} · {new Date(log.created_at).toLocaleString()}</p>
              </div>
              <span className={`text-xs uppercase px-2 py-1 rounded ${log.status === 'success' ? 'bg-green-500/10 text-green-700 dark:text-green-400' : 'bg-red-500/10 text-red-700 dark:text-red-400'}`}>
                {log.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {tab === 'activity-logs' && (
        <div className="space-y-2">
          {activityLogs.data?.length === 0 && <p className="text-sm text-muted-foreground p-4 border rounded-lg">No activity logged yet.</p>}
          {activityLogs.data?.map((log) => (
            <div key={log.id} className="p-3 border rounded-lg flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{log.action}</p>
                <p className="text-xs text-muted-foreground">{log.entity_type}</p>
              </div>
              <span className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
