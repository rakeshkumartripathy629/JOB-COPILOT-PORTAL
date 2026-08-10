import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { KeyRound, Loader2 } from 'lucide-react'
import api from '../services/api'
import { getApiError } from '../utils/apiError'
import { Button } from '../components/ui/button'

export default function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'request' | 'reset'>('request')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [busy, setBusy] = useState(false)

  async function requestCode(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true)
    try {
      const { data } = await api.post<{ message: string; reset_code: string }>('/auth/forgot-password', { email })
      setCode(data.reset_code)
      setStep('reset')
      toast.success('Reset code generated')
    } catch (err) {
      toast.error(getApiError(err))
    } finally {
      setBusy(false)
    }
  }

  async function reset(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post('/auth/reset-password', {
        email,
        code,
        new_password: newPassword,
      })
      toast.success('Password reset! Please log in.')
      navigate('/login')
    } catch (err) {
      toast.error(getApiError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4 border rounded-lg p-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <KeyRound className="h-5 w-5" />
          Reset Password
        </h1>

        {step === 'request' ? (
          <form onSubmit={requestCode} className="space-y-4">
            <label className="block text-sm">
              <span className="text-muted-foreground">Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full mt-1 p-2 border rounded bg-background"
              />
            </label>
            <Button type="submit" disabled={busy} className="w-full flex items-center justify-center gap-2">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              Get Reset Code
            </Button>
          </form>
        ) : (
          <form onSubmit={reset} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Your reset code is <span className="font-mono font-semibold text-foreground">{code}</span>. Enter it with
              your new password. The code expires in 10 minutes.
            </p>
            <label className="block text-sm">
              <span className="text-muted-foreground">Reset code</span>
              <input
                type="text"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="w-full mt-1 p-2 border rounded bg-background"
              />
            </label>
            <label className="block text-sm">
              <span className="text-muted-foreground">New password</span>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full mt-1 p-2 border rounded bg-background"
              />
            </label>
            <Button type="submit" disabled={busy} className="w-full flex items-center justify-center gap-2">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              Reset Password
            </Button>
          </form>
        )}

        <button
          onClick={() => navigate('/login')}
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to login
        </button>
      </div>
    </div>
  )
}
