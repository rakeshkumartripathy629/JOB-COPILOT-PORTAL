import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, LogOut, Moon, Sun, Sparkles } from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import api from '../../services/api'
import { User } from '../../types'

export function Header() {
  const navigate = useNavigate()
  const { theme, toggle } = useThemeStore()
  const logout = useAuthStore((s) => s.logout)
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get('/users/me')).data as User,
  })
  const { data: notifCount } = useQuery({
    queryKey: ['notif-unread'],
    queryFn: async () => (await api.get('/notifications/unread-count')).data as { unread: number },
    refetchInterval: 30000,
  })
  const unread = notifCount?.unread ?? 0

  async function handleLogout() {
    try {
      await api.post('/auth/logout')
    } catch {
      // ignore: still clear local session
    }
    logout()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card/70 px-4 backdrop-blur sm:px-6">
      <Link to="/dashboard" className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary via-violet-500 to-fuchsia-500 text-white shadow-sm">
          <Sparkles className="h-4 w-4" />
        </span>
        <span className="hidden text-base font-semibold sm:block">AI Job Copilot</span>
      </Link>
      <div className="flex items-center gap-1.5">
        <Link
          to="/notifications"
          className="relative rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          title="Notifications"
        >
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute right-1 top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-600 px-1 text-[10px] font-semibold text-white">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </Link>
        <button
          onClick={toggle}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          title="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <span className="hidden items-center gap-2 rounded-full bg-accent px-3 py-1 text-sm font-medium text-accent-foreground sm:flex">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
            {(me?.full_name ?? '?').charAt(0).toUpperCase()}
          </span>
          {me?.full_name}
        </span>
        <button
          onClick={handleLogout}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          title="Logout"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}
