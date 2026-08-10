import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Lock, Mail, Sparkles, User } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import { Button } from '../components/ui/button'

export default function SignupPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [alreadyRegistered, setAlreadyRegistered] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setAlreadyRegistered(false)
    try {
      await api.post('/auth/signup', { email, password, full_name: fullName })
      window.location.href = '/login'
    } catch (err: unknown) {
      const message = getApiError(err)
      setError(message)
      setAlreadyRegistered(message.toLowerCase().includes('already registered'))
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
          <h1 className="mt-4 text-2xl font-bold tracking-tight">Create your account</h1>
          <p className="mt-1 text-sm text-muted-foreground">Start matching jobs to your resume</p>
        </div>
        {error && <p className="mb-4 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        {alreadyRegistered && (
          <p className="mb-4 rounded-lg bg-primary/10 px-3 py-2 text-sm text-primary">
            Already have an account?{' '}
            <Link to="/login" className="font-medium underline">
              Log in
            </Link>
          </p>
        )}
        <form onSubmit={submit} className="space-y-4">
          <label className="space-y-1.5 text-sm">
            <span className="font-medium text-muted-foreground">Full Name</span>
            <div className="relative">
              <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input type="text" placeholder="Jane Doe" value={fullName} onChange={(e) => setFullName(e.target.value)} className="input pl-9" required />
            </div>
          </label>
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
              <input type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} className="input pl-9" required minLength={8} />
            </div>
          </label>
          <Button type="submit" className="w-full" size="lg">
            Sign Up
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Login
          </Link>
        </p>
      </div>
    </div>
  )
}
