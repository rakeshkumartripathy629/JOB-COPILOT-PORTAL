import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Home,
  FileText,
  Briefcase,
  ClipboardList,
  FileText as Letter,
  MessageSquare,
  Bot,
  Bell,
  Shield,
  Sparkles,
  LineChart,
  Database,
} from 'lucide-react'
import { cn } from '../../utils/cn'
import api from '../../services/api'
import { User } from '../../types'

const groups: { label: string; items: { to: string; icon: typeof Home; label: string }[] }[] = [
  {
    label: 'Overview',
    items: [{ to: '/dashboard', icon: Home, label: 'Dashboard' }],
  },
  {
    label: 'Your toolkit',
    items: [
      { to: '/resume', icon: FileText, label: 'Resume' },
      { to: '/jobs', icon: Briefcase, label: 'Jobs' },
      { to: '/vault', icon: Database, label: 'Career Vault' },
      { to: '/intel', icon: LineChart, label: 'Market Intel' },
      { to: '/applications', icon: ClipboardList, label: 'Applications' },
      { to: '/cover-letters', icon: Letter, label: 'Cover Letters' },
      { to: '/interview-prep', icon: MessageSquare, label: 'Interview Prep' },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/automation', icon: Bot, label: 'Automation' },
      { to: '/notifications', icon: Bell, label: 'Notifications' },
    ],
  },
]

export function Sidebar() {
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get('/users/me')).data as User,
  })

  const visibleGroups = groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.to !== '/admin' || me?.is_superuser),
    }))
    .filter((group) => group.items.length > 0)

  if (me?.is_superuser) {
    visibleGroups[visibleGroups.length - 1].items.push({ to: '/admin', icon: Shield, label: 'Admin' })
  }

  return (
    <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-64 shrink-0 border-r border-border bg-card/60 backdrop-blur lg:block">
      <nav className="flex flex-col gap-6 p-4">
        <div className="flex items-center gap-3 px-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-violet-500 to-fuchsia-500 text-white shadow-md">
            <Sparkles className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">AI Job Copilot</p>
            <p className="text-xs text-muted-foreground">Your career co-pilot</p>
          </div>
        </div>

        {visibleGroups.map((group) => (
          <div key={group.label} className="space-y-1">
            <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
              {group.label}
            </p>
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all',
                    isActive
                      ? 'bg-gradient-to-r from-primary to-violet-600 text-white shadow-sm'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon
                      className={cn(
                        'h-4 w-4 transition-colors',
                        isActive ? 'text-white' : 'text-muted-foreground group-hover:text-primary',
                      )}
                    />
                    {item.label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  )
}
