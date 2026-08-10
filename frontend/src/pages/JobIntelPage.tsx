import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Building2,
  Clock,
  DollarSign,
  Globe,
  LineChart,
  Sparkles,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react'
import api from '../services/api'
import {
  CareerIntel,
  CompanyIntel,
  JobIntelSummary,
  SalaryBenchmark,
  SkillDemand,
  TrendPoint,
} from '../types'
import { cn } from '../utils/cn'

type CountryFilter = '' | 'India'

const fmtCurrency = (n: number | null | undefined) =>
  n == null ? '—' : `$${n.toLocaleString()}`
const fmtCompact = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString()

export default function JobIntelPage() {
  const [country, setCountry] = useState<CountryFilter>('')

  const { data: summary } = useQuery({
    queryKey: ['intel-summary', country],
    queryFn: async () =>
      (await api.get(`/jobs/intel/summary${country ? `?country=${country}` : ''}`)).data as JobIntelSummary,
  })

  const { data: skills } = useQuery({
    queryKey: ['intel-skills', country],
    queryFn: async () =>
      (await api.get(`/jobs/intel/skills?limit=12${country ? `&country=${country}` : ''}`)).data as SkillDemand[],
  })

  const { data: companies } = useQuery({
    queryKey: ['intel-companies', country],
    queryFn: async () =>
      (await api.get(`/jobs/intel/companies?limit=8${country ? `&country=${country}` : ''}`)).data as CompanyIntel[],
  })

  const { data: salary } = useQuery({
    queryKey: ['intel-salary', country],
    queryFn: async () =>
      (await api.get(`/jobs/intel/salary${country ? `&country=${country}` : ''}`)).data as SalaryBenchmark[],
  })

  const { data: trends } = useQuery({
    queryKey: ['intel-trends', country],
    queryFn: async () =>
      (await api.get(`/jobs/intel/trends?days=30${country ? `&country=${country}` : ''}`)).data as TrendPoint[],
  })

  const { data: profile } = useQuery({
    queryKey: ['intel-profile'],
    queryFn: async () => (await api.get('/jobs/intel/profile')).data as CareerIntel,
  })

  const maxSkillCount = Math.max(1, ...(skills?.map((s) => s.count) ?? [1]))
  const maxTrend = Math.max(1, ...(trends?.map((t) => t.count) ?? [1]))

  const cards = [
    {
      label: 'Jobs tracked',
      value: fmtCompact(summary?.total_jobs),
      icon: Globe,
      grad: 'from-primary to-violet-600',
    },
    {
      label: 'Companies hiring',
      value: fmtCompact(summary?.distinct_companies),
      icon: Building2,
      grad: 'from-fuchsia-500 to-pink-600',
    },
    {
      label: 'Median salary',
      value: fmtCurrency(summary?.median_salary),
      icon: DollarSign,
      grad: 'from-emerald-500 to-teal-600',
    },
    {
      label: 'Remote share',
      value: summary ? `${summary.remote_share_pct}%` : '—',
      icon: Users,
      grad: 'from-amber-500 to-orange-600',
    },
    {
      label: 'Postings · 30d',
      value: fmtCompact(summary?.jobs_posted_30d),
      icon: Clock,
      grad: 'from-sky-500 to-blue-600',
    },
    {
      label: 'Demand index',
      value: summary ? `${summary.demand_index}%` : '—',
      icon: TrendingUp,
      grad: 'from-rose-500 to-red-600',
    },
  ]

  return (
    <div className="space-y-8 animate-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Market <span className="text-gradient">Intelligence</span>
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <LineChart className="h-4 w-4" />
            Live signals from {summary?.total_jobs ?? '…'} jobs in your database
          </p>
        </div>
        <select
          aria-label="Filter intelligence by location"
          value={country}
          onChange={(e) => setCountry(e.target.value as CountryFilter)}
          className="input w-auto cursor-pointer"
        >
          <option value="">All locations</option>
          <option value="India">India</option>
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
        {cards.map((c) => (
          <div key={c.label} className="card group p-4 transition-shadow hover:shadow-lift">
            <span
              className={cn(
                'flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm transition-transform duration-200 group-hover:scale-110',
                c.grad,
              )}
            >
              <c.icon className="h-4 w-4" />
            </span>
            <p className="mt-3 text-xl font-bold tabular-nums">{c.value}</p>
            <p className="text-xs text-muted-foreground">{c.label}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <section className="card space-y-4 p-5 lg:col-span-2">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            <h2 className="text-lg font-semibold">Personalized Career Intel</h2>
          </div>
          {profile?.has_resume ? (
            <div className="space-y-5">
              <div className="flex items-center gap-4">
                <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
                  <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
                    <circle cx="18" cy="18" r="15.5" fill="none" className="stroke-muted" strokeWidth="4" />
                    <circle
                      cx="18"
                      cy="18"
                      r="15.5"
                      fill="none"
                      className="stroke-primary"
                      strokeWidth="4"
                      strokeLinecap="round"
                      strokeDasharray={`${(profile.coverage_score / 100) * 97.4} 97.4`}
                    />
                  </svg>
                  <span className="absolute text-sm font-bold">{profile.coverage_score}%</span>
                </div>
                <div className="text-sm">
                  <p className="font-medium">Resume covers {profile.coverage_score}% of in-demand skills</p>
                  <p className="mt-1 text-muted-foreground">
                    {profile.target_jobs_count} jobs match your profile · median{' '}
                    {fmtCurrency(profile.median_target_salary)}
                  </p>
                </div>
              </div>
              {profile.user_skills.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Your skills in demand
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.user_skills.map((s) => (
                      <span key={s.skill} className="badge bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                        {s.skill}
                        <span className="opacity-70">· {s.jobs_count}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {profile.recommended_skills.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Skills to learn next
                  </p>
                  <div className="space-y-2">
                    {profile.recommended_skills.slice(0, 6).map((s) => (
                      <div key={s.skill} className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2 text-sm">
                        <span className="font-medium">{s.skill}</span>
                        <span className="text-xs text-muted-foreground">{s.count} jobs</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
              Upload a resume on the <span className="font-medium text-foreground">Resume</span> page to get
              personalized skill-demand analysis and salary targets.
            </p>
          )}
        </section>

        <section className="card space-y-4 p-5 lg:col-span-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-amber-500" />
            <h2 className="text-lg font-semibold">Most in-demand skills</h2>
          </div>
          <div className="space-y-2.5">
            {skills && skills.length > 0 ? (
              skills.map((s, i) => (
                <div key={s.skill} className="flex items-center gap-3">
                  <span className="w-5 text-right text-xs tabular-nums text-muted-foreground">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="truncate font-medium">{s.skill}</span>
                      <span className="ml-2 shrink-0 tabular-nums text-xs text-muted-foreground">{s.count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-primary via-violet-500 to-fuchsia-500"
                        style={{ width: `${(s.count / maxSkillCount) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No skill data yet — refresh jobs to enrich the corpus.</p>
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card space-y-4 p-5">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <h2 className="text-lg font-semibold">Posting activity · 30 days</h2>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends ?? []} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d: string) => d.slice(5)} stroke="hsl(var(--muted-foreground))" />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" domain={[0, maxTrend]} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 12 }}
                  labelFormatter={(d) => `Date: ${d}`}
                />
                <Area type="monotone" dataKey="count" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#trendFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="card space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-primary" />
            <h2 className="text-lg font-semibold">Top hiring companies</h2>
          </div>
          <div className="space-y-2">
            {companies && companies.length > 0 ? (
              companies.map((c) => (
                <div key={c.company} className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2.5 text-sm">
                  <span className="truncate font-medium">{c.company}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {c.job_count} jobs{c.avg_salary ? ` · ${fmtCompact(c.avg_salary)}` : ''}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No company data yet.</p>
            )}
          </div>
        </section>
      </div>

      <section className="card space-y-4 p-5">
        <div className="flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-emerald-500" />
          <h2 className="text-lg font-semibold">Salary benchmarks by seniority</h2>
        </div>
        {salary && salary.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Seniority</th>
                  <th className="pb-2 pr-4 text-right font-medium">Jobs</th>
                  <th className="pb-2 pr-4 text-right font-medium">P25</th>
                  <th className="pb-2 pr-4 text-right font-medium">Median</th>
                  <th className="pb-2 pr-4 text-right font-medium">P75</th>
                  <th className="pb-2 text-right font-medium">Avg</th>
                </tr>
              </thead>
              <tbody>
                {salary.map((row) => (
                  <tr key={row.seniority} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5 pr-4 font-medium">{row.seniority}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-muted-foreground">{row.count}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{fmtCurrency(row.p25)}</td>
                    <td className="py-2.5 pr-4 text-right font-semibold tabular-nums">{fmtCurrency(row.median_salary)}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{fmtCurrency(row.p75)}</td>
                    <td className="py-2.5 text-right tabular-nums text-muted-foreground">{fmtCurrency(row.avg_salary)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No salary data yet.</p>
        )}
      </section>
    </div>
  )
}
