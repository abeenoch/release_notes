import { useState } from 'react'
import type { FormEvent } from 'react'
import { Mail, Check, Loader2 } from 'lucide-react'
import { publicApi } from '../lib'

/**
 * "Get release notes by email" card on the public changelog page.
 * Double opt-in: this only starts the flow — a confirmation mail goes out
 * through the repo owner's own SMTP/SendGrid config.
 */
export function SubscribeCard({ owner, repo }: { owner: string; repo: string }) {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'done'>('idle')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const value = email.trim()
    if (!value || state === 'sending') return
    setState('sending')
    setError('')
    try {
      const res = await publicApi.subscribe(owner, repo, value)
      setMessage(res.message)
      setState('done')
    } catch (err) {
      setError((err as Error).message)
      setState('idle')
    }
  }

  if (state === 'done') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 dark:border-emerald-900 dark:bg-emerald-950/40">
        <Check size={18} className="mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <p className="text-sm text-emerald-800 dark:text-emerald-300">{message}</p>
      </div>
    )
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="flex items-center gap-2">
        <Mail size={16} className="text-zinc-400" />
        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Get release notes by email</p>
      </div>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => { setEmail(e.target.value); setError('') }}
          placeholder="you@example.com"
          className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
        />
        <button
          type="submit"
          disabled={state === 'sending'}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          {state === 'sending' ? <Loader2 size={14} className="animate-spin" /> : null}
          {state === 'sending' ? 'Subscribing…' : 'Subscribe'}
        </button>
      </div>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        One confirmation email first — no mail until you click the link.
      </p>
      {error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </form>
  )
}
