import { useEffect, useState } from 'react'
import { Loader2, Trash2, Pencil, Check } from 'lucide-react'
import { notifyApi } from '../lib'
import type { NotifyConfig } from '../lib'
import { BrandIcon } from '../components/BrandIcon'
import { ConfirmButton } from '../components/ConfirmButton'
import { ProviderDropdown } from '../components/ProviderDropdown'

const NOTIFY_PROVIDERS = [
  { id: 'smtp', label: 'Email (SMTP)' },
  { id: 'slack', label: 'Slack' },
]

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

  // Edit-in-place state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editSlackUrl, setEditSlackUrl] = useState('')
  const [editChannel, setEditChannel] = useState('')
  const [editFrom, setEditFrom] = useState('')
  const [editTo, setEditTo] = useState('')
  const [editHost, setEditHost] = useState('')
  const [editUser, setEditUser] = useState('')
  const [editPass, setEditPass] = useState('')

  const startEdit = (c: NotifyConfig) => {
    setEditingId(c.id)
    setEditSlackUrl(c.slack_webhook_url ?? '')
    setEditChannel(c.slack_channel ?? '')
    setEditFrom(c.from_email ?? '')
    setEditTo(c.to_email ?? '')
    setEditHost(c.smtp_host ?? '')
    setEditUser(c.smtp_user ?? '')
    setEditPass('')
  }

  const saveEdit = async (id: string) => {
    setError('')
    setSaving(true)
    try {
      const cur = configs.find((c) => c.id === id)
      const payload: Record<string, unknown> = {}
      if (cur?.provider === 'slack') {
        if (editSlackUrl !== (cur.slack_webhook_url ?? '')) payload.slack_webhook_url = editSlackUrl || null
        if (editChannel !== (cur.slack_channel ?? '')) payload.slack_channel = editChannel || null
      } else {
        if (editHost !== (cur?.smtp_host ?? '')) payload.smtp_host = editHost || null
        if (editUser !== (cur?.smtp_user ?? '')) payload.smtp_user = editUser || null
        if (editFrom !== (cur?.from_email ?? '')) payload.from_email = editFrom || null
        if (editTo !== (cur?.to_email ?? '')) payload.to_email = editTo || null
        if (editPass.trim()) payload.smtp_pass = editPass.trim()
      }
      await notifyApi.update(id, payload)
      setEditingId(null)
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const activate = async (c: NotifyConfig) => {
    if (c.is_active) return
    try {
      await notifyApi.update(c.id, { is_active: true })
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
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
          <ProviderDropdown
            value={provider}
            options={NOTIFY_PROVIDERS}
            onChange={(id) => setProvider(id)}
          />
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
            <div key={c.id}
              className={`rounded-xl border bg-white dark:bg-zinc-900 ${editingId === c.id ? 'border-brand-300 dark:border-brand-700' : 'border-zinc-200 dark:border-zinc-800'}`}>
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <BrandIcon provider={c.provider} size={18} />
                  <div>
                    <span className="flex items-center gap-2 text-sm font-medium capitalize text-zinc-900 dark:text-zinc-50">
                      {c.provider}
                      {c.is_active
                        ? <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">active</span>
                        : <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">inactive</span>}
                    </span>
                    <p className="text-xs text-zinc-400">
                      {c.provider === 'slack'
                        ? `${c.slack_channel || 'channel'} · webhook ${c.slack_webhook_url ? 'saved' : 'missing'}`
                        : `${c.smtp_host || 'SMTP'} · ${c.from_email || '?'} → ${c.to_email || '?'}${c.has_smtp_pass ? '' : ' · no password'}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {!c.is_active && (
                    <button onClick={() => activate(c)}
                      className="rounded-lg px-2.5 py-2 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-500/10">
                      Activate
                    </button>
                  )}
                  <button onClick={() => startEdit(c)}
                    className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                    title="Edit config">
                    <Pencil size={15} />
                  </button>
                  <ConfirmButton onConfirm={() => remove(c.id)} title="Delete config">
                    <Trash2 size={16} />
                  </ConfirmButton>
                </div>
              </div>

              {editingId === c.id && (
                <div className="border-t border-zinc-200 px-5 py-4 dark:border-zinc-800">
                  {c.provider === 'slack' ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="sm:col-span-2">
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Slack webhook URL</label>
                        <input value={editSlackUrl} onChange={(e) => setEditSlackUrl(e.target.value)}
                          placeholder="https://hooks.slack.com/…" className={inputCls} />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Channel</label>
                        <input value={editChannel} onChange={(e) => setEditChannel(e.target.value)}
                          placeholder="#releases" className={inputCls} />
                      </div>
                    </div>
                  ) : (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">SMTP host</label>
                        <input value={editHost} onChange={(e) => setEditHost(e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">SMTP user</label>
                        <input value={editUser} onChange={(e) => setEditUser(e.target.value)} className={inputCls} />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Password {c.has_smtp_pass ? <span className="text-zinc-400">(blank keeps current)</span> : <span className="text-amber-600">* needed</span>}</label>
                        <input type="password" value={editPass} onChange={(e) => setEditPass(e.target.value)}
                          placeholder={c.has_smtp_pass ? '••••••••' : 'SMTP password'} className={inputCls} />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">From email</label>
                        <input value={editFrom} onChange={(e) => setEditFrom(e.target.value)} className={inputCls} />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">To recipients <span className="text-zinc-400">(comma-separated)</span></label>
                        <input value={editTo} onChange={(e) => setEditTo(e.target.value)} className={inputCls} />
                      </div>
                    </div>
                  )}
                  <div className="mt-3 flex items-center gap-2">
                    <button onClick={() => saveEdit(c.id)} disabled={saving}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                      {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Save
                    </button>
                    <button onClick={() => setEditingId(null)} disabled={saving}
                      className="rounded-lg px-3.5 py-2 text-sm font-medium text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 dark:text-zinc-400">
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
