import { useEffect, useState } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import { notifyApi } from '../lib'
import type { NotifyConfig } from '../lib'
import { BrandIcon } from '../components/BrandIcon'
import { ConfirmButton } from '../components/ConfirmButton'

export function NotificationsPage() {
  const [configs, setConfigs] = useState<NotifyConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [provider, setProvider] = useState('smtp')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUser, setSmtpUser] = useState('')
  const [smtpPass, setSmtpPass] = useState('')
  const [fromEmail, setFromEmail] = useState('')
  const [toEmail, setToEmail] = useState('')
  const [slackUrl, setSlackUrl] = useState('')
  const [slackChannel, setSlackChannel] = useState('')

  const load = () => notifyApi.list().then((r) => setConfigs(r.configs)).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const create = async () => {
    setError('')
    setSaving(true)
    try {
      const body: Record<string, unknown> = { provider }
      if (provider === 'smtp') {
        body.smtp_host = smtpHost
        body.smtp_port = parseInt(smtpPort, 10) || 587
        body.smtp_user = smtpUser || null
        body.smtp_pass = smtpPass || null
        body.from_email = fromEmail || null
        // Convert newline-separated recipients to comma-separated for SMTP
        body.to_email = toEmail ? toEmail.split('\n').map(s => s.trim()).filter(Boolean).join(', ') : null
      } else {
        body.slack_webhook_url = slackUrl
        body.slack_channel = slackChannel || null
      }
      await notifyApi.create(body)
      setSmtpPass(''); setSlackUrl(''); setSlackChannel('')
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    await notifyApi.remove(id)
    await load()
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="animate-spin text-zinc-400" size={24} />
      </div>
    )
  }

  const inputCls = 'w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100'
  const labelCls = 'mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Notifications</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">Where finished changelogs get delivered.</p>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-4 max-w-xs">
          <label className={labelCls}>Provider</label>
          <div className="flex items-center gap-2">
            <select value={provider} onChange={(e) => setProvider(e.target.value)} className={inputCls}>
              <option value="smtp">Email (SMTP)</option>
              <option value="slack">Slack</option>
            </select>
            <BrandIcon provider={provider} size={18} />
          </div>
        </div>

        {provider === 'smtp' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className={labelCls}>SMTP host</label>
              <input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.example.com" className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Port</label>
              <input value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} placeholder="587" className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Username</label>
              <input value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Password</label>
              <input type="password" value={smtpPass} onChange={(e) => setSmtpPass(e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>From email</label>
              <input value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} placeholder="releases@example.com" className={inputCls} />
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>To recipients <span className="text-zinc-400">(one per line)</span></label>
              <textarea
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                placeholder={"alice@example.com\nbob@example.com"}
                rows={3}
                className={inputCls + ' resize-y min-h-[70px]'}
              />
            </div>
            </div>
          ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className={labelCls}>Slack webhook URL</label>
              <input value={slackUrl} onChange={(e) => setSlackUrl(e.target.value)} placeholder="https://hooks.slack.com/…" className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Channel (optional)</label>
              <input value={slackChannel} onChange={(e) => setSlackChannel(e.target.value)} placeholder="#releases" className={inputCls} />
            </div>
          </div>
        )}

        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button onClick={create} disabled={saving}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
          {saving && <Loader2 size={16} className="animate-spin" />}
          Save notification config
        </button>
      </div>

      <div className="space-y-2">
        {configs.length === 0 ? (
          <p className="rounded-xl border border-zinc-200 bg-white px-5 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            No notification channels configured yet.
          </p>
        ) : (
          configs.map((c) => (
            <div key={c.id} className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center gap-3">
                <BrandIcon provider={c.provider} size={18} />
                <div>
                  <span className="text-sm font-medium capitalize text-zinc-900 dark:text-zinc-50">{c.provider}</span>
                  <p className="text-xs text-zinc-400">
                    {c.provider === 'slack'
                      ? `${c.slack_channel || 'channel'} · webhook saved`
                      : `${c.smtp_host || 'SMTP'} · ${c.from_email || '?'} → ${c.to_email || '?'}`}
                  </p>
                </div>
              </div>
              <ConfirmButton onConfirm={() => remove(c.id)} title="Delete config">
                <Trash2 size={16} />
              </ConfirmButton>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
