import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Lock, Mail, Sparkles } from 'lucide-react'
import api from '../services/api'
import { useAuthStore } from '../store/authStore'
import { getApiError } from '../utils/apiError'
import { Button } from '../components/ui/button'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const setAuth = useAuthStore((s) => s.setAuth)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const res = await api.post('/auth/login', { email, password })
      setAuth(res.data.access_token, { email })
      window.location.href = '/dashboard'
    } catch (err: unknown) {
      setError(getApiError(err))
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div className="pointer-events-none absolute -top-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-gradient-to-br from-primary/25 via-violet-500/20 to-fuchsia-500/25 blur-3xl" />
      <div className="animate-in card relative w-full max-w-sm p-8 shadow-lift">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary via-violet-500 to-fuchsia-500 text-white shadow-md">
            <Sparkles className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-2xl font-bold tracking-tight">Welcome back</h1>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to your AI Job Copilot</p>
        </div>
        {error && <p className="mb-4 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <form onSubmit={submit} className="space-y-4">
          <label className="space-y-1.5 text-sm">
            <span className="font-medium text-muted-foreground">Email</span>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} className="input pl-9" required />
            </div>
          </label>
          <label className="space-y-1.5 text-sm">
            <span className="font-medium text-muted-foreground">Password</span>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} className="input pl-9" required />
            </div>
          </label>
          <Button type="submit" className="w-full" size="lg">
            Login
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          New here?{' '}
          <Link to="/signup" className="font-medium text-primary hover:underline">
            Create an account
          </Link>
          <span className="mx-2 text-border">·</span>
          <Link to="/forgot-password" className="font-medium text-primary hover:underline">
            Forgot password?
          </Link>
        </p>
      </div>
    </div>
  )
}
