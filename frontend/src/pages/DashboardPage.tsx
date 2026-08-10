import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  BarChart3,
  Bell,
  Briefcase,
  ClipboardList,
  FileText,
  Lightbulb,
  MessageSquare,
  Percent,
  Target,
  UserCircle,
} from "lucide-react";
import api from "../services/api";
import { getApiError } from "../utils/apiError";
import { AnalyticsSummary, Application, Notification, User } from "../types";
import { Button } from "../components/ui/button";
import { cn } from "../utils/cn";

const cardStyles = [
  "from-primary to-violet-600",
  "from-fuchsia-500 to-pink-600",
  "from-emerald-500 to-teal-600",
  "from-amber-500 to-orange-600",
];

export default function DashboardPage() {
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await api.get("/users/me")).data as User,
  });
  const { data: apps } = useQuery({
    queryKey: ["apps"],
    queryFn: async () => (await api.get("/applications")).data as Application[],
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics"],
    queryFn: async () =>
      (await api.get("/analytics/me")).data as {
        metrics: AnalyticsSummary;
        insights: string[];
      },
  });

  const { data: notifs } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () =>
      (await api.get("/notifications")).data as Notification[],
  });

  const m = analytics?.metrics;
  const cards = [
    {
      label: "Applications",
      value: m?.total_applications ?? apps?.length ?? 0,
      icon: ClipboardList,
      to: "/applications",
    },
    {
      label: "Interviews",
      value: m?.interviews ?? 0,
      icon: MessageSquare,
      to: "/interview-prep",
    },
    {
      label: "Response Rate",
      value: `${m?.response_rate_percent ?? 0}%`,
      icon: Percent,
      to: "/applications",
    },
    {
      label: "Cover Letters",
      value: m?.cover_letters ?? 0,
      icon: FileText,
      to: "/cover-letters",
    },
  ];

  return (
    <div className="space-y-8 animate-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Welcome back, <span className="text-gradient">{me?.full_name?.split(" ")[0] ?? "there"}</span>
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <BarChart3 className="h-4 w-4" />
            Here is your job-search overview
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map((c, i) => (
          <Link
            key={c.label}
            to={c.to}
            className="card group p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift"
          >
            <span
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm transition-transform duration-200 group-hover:scale-110",
                cardStyles[i % cardStyles.length],
              )}
            >
              <c.icon className="h-5 w-5" />
            </span>
            <p className="mt-4 text-2xl font-bold tabular-nums">{c.value}</p>
            <p className="text-sm text-muted-foreground">{c.label}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-500" />
            <h2 className="text-lg font-semibold">Insights</h2>
          </div>
          <div className="space-y-2">
            {analytics?.insights.length ? (
              analytics.insights.map((insight, i) => (
                <p
                  key={i}
                  className="rounded-xl border border-border bg-card p-4 text-sm shadow-soft transition-shadow hover:shadow-lift"
                >
                  {insight}
                </p>
              ))
            ) : (
              <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                No insights yet — start tracking applications to see AI-powered tips here.
              </p>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-primary" />
              <h2 className="text-lg font-semibold">Recent Notifications</h2>
            </div>
            <Link
              to="/notifications"
              className="text-sm font-medium text-primary hover:underline"
            >
              View all
            </Link>
          </div>
          <div className="space-y-2">
            {notifs?.length === 0 && (
              <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                No notifications yet.
              </p>
            )}
            {notifs?.slice(0, 5).map((n) => (
              <div
                key={n.id}
                className={cn(
                  "rounded-xl border bg-card p-4 shadow-soft",
                  n.is_read ? "border-border" : "border-primary/40",
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      n.is_read ? "bg-muted-foreground/50" : "bg-gradient-to-br from-primary to-violet-600",
                    )}
                  />
                  <p className="text-sm font-medium">{n.title}</p>
                </div>
                {n.message && (
                  <p className="mt-1 text-xs text-muted-foreground">{n.message}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Briefcase className="h-4 w-4 text-primary" />
          <h2 className="text-lg font-semibold">Applications by Status</h2>
        </div>
        {m && Object.keys(m.applications_by_status).length > 0 ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {Object.entries(m.applications_by_status).map(([status, count]) => (
              <div key={status} className="card p-4 transition-shadow hover:shadow-lift">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {status}
                </p>
                <p className="mt-1 flex items-center gap-2 text-xl font-bold tabular-nums">
                  <Target className="h-4 w-4 text-muted-foreground" />
                  {count}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            No applications tracked yet.
          </p>
        )}
      </section>

      <ProfileEditor user={me} />
    </div>
  );
}

function ProfileEditor({ user }: { user: User | undefined }) {
  const qc = useQueryClient();
  const profile = user?.profile ?? null;
  const [headline, setHeadline] = useState(profile?.headline ?? "");
  const [phone, setPhone] = useState(profile?.phone ?? "");
  const [location, setLocation] = useState(profile?.location ?? "");
  const [summary, setSummary] = useState(profile?.summary ?? "");

  const save = useMutation({
    mutationFn: async () =>
      (
        await api.patch("/users/me", {
          headline: headline.trim() || null,
          phone: phone.trim() || null,
          location: location.trim() || null,
          summary: summary.trim() || null,
        })
      ).data as User,
    onSuccess: () => {
      toast.success("Profile updated");
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err) => toast.error(getApiError(err)),
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <UserCircle className="h-4 w-4 text-primary" />
        <h2 className="text-lg font-semibold">Profile</h2>
      </div>
      <form
        onSubmit={onSubmit}
        className="card grid gap-4 p-5 md:grid-cols-2"
      >
        <label className="space-y-1.5 text-sm">
          <span className="font-medium text-muted-foreground">Headline</span>
          <input
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="e.g. Senior Full-Stack Engineer"
            className="input"
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium text-muted-foreground">Phone</span>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 555 000 0000"
            className="input"
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium text-muted-foreground">Location</span>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Bengaluru, India"
            className="input"
          />
        </label>
        <div className="flex items-end">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save Profile"}
          </Button>
        </div>
        <label className="space-y-1.5 text-sm md:col-span-2">
          <span className="font-medium text-muted-foreground">Summary</span>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Short professional summary"
            rows={3}
            className="input"
          />
        </label>
      </form>
    </section>
  );
}
