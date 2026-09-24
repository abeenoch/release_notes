import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Loader2, CheckCircle2, XCircle, MailX } from 'lucide-react'
import { publicApi } from '../lib'
import type { TokenActionResult } from '../lib'

/**
 * Landing page for links in confirmation/unsubscription emails:
 * /confirm/:token and /unsubscribe/:token (both public routes).
 */
export function TokenActionPage({ action }: { action: 'confirm' | 'unsubscribe' }) {
  const { token } = useParams()
  const [result, setResult] = useState<TokenActionResult | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    const call = action === 'confirm' ? publicApi.confirm : publicApi.unsubscribe
    call(token)
      .then((r) => { if (!cancelled) setResult(r) })
      .catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [action, token])

  if (!result && !failed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Loader2 className="animate-spin text-zinc-400" size={24} />
      </div>
    )
  }

  const ok = result && result.status !== 'not_found'
  const icon = failed || !ok
    ? <XCircle size={40} className="text-red-400" />
    : action === 'confirm'
      ? <CheckCircle2 size={40} className="text-emerald-500" />
      : <MailX size={40} className="text-zinc-400" />

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 px-4 text-center dark:bg-zinc-950">
      {icon}
      <div>
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          {failed
            ? 'Something went wrong'
            : result?.status === 'confirmed'
              ? 'Subscription confirmed'
              : result?.status === 'unsubscribed'
                ? 'Unsubscribed'
                : 'Link not valid'}
        </h1>
        <p className="mt-1 max-w-md text-sm text-zinc-500 dark:text-zinc-400">
          {failed
            ? 'Please try again in a moment.'
            : result?.message}
        </p>
      </div>
      <Link to="/" className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-400">
        Release Notes — go to app
      </Link>
    </div>
  )
}
