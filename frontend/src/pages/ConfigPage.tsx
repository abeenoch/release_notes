import { useEffect, useState } from 'react'
import { Loader2, Trash2, Check, Pencil } from 'lucide-react'
import { configApi } from '../lib'
import type { LlmConfig } from '../lib'
import { BrandIcon } from '../components/BrandIcon'
import { ConfirmButton } from '../components/ConfirmButton'
import { ProviderDropdown } from '../components/ProviderDropdown'

const PROVIDERS = [
  { id: 'commit', label: 'Commit Parser (no LLM)', needsKey: false },
  { id: 'openai', label: 'OpenAI', needsKey: true },
  { id: 'anthropic', label: 'Anthropic', needsKey: true },
  { id: 'groq', label: 'Groq', needsKey: true },
  { id: 'openrouter', label: 'OpenRouter', needsKey: true },
  { id: 'ollama', label: 'Ollama (local)', needsKey: false },
]

export function ConfigPage() {
  const [configs, setConfigs] = useState<LlmConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [provider, setProvider] = useState('commit')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  // Edit-in-place state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editKey, setEditKey] = useState('')
  const [editModel, setEditModel] = useState('')
  const [editBaseUrl, setEditBaseUrl] = useState('')

  const load = () =>
    configApi.listLlms().then(setConfigs).finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const needsKey = PROVIDERS.find((p) => p.id === provider)?.needsKey

  const create = async () => {
    setError('')
    if (needsKey && !apiKey) { setError('API key is required for this provider'); return }
    setSaving(true)
    try {
      await configApi.createLlm({ provider, api_key: apiKey || undefined, model: model || undefined, base_url: baseUrl || undefined })
      setApiKey(''); setModel(''); setBaseUrl('')
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    await configApi.removeLlm(id)
    await load()
  }

  const startEdit = (c: LlmConfig) => {
    setEditingId(c.id)
    setEditKey('')
    setEditModel(c.model ?? '')
    setEditBaseUrl(c.base_url ?? '')
  }

  const saveEdit = async (id: string) => {
    setError('')
    setSaving(true)
    try {
      const payload: Record<string, unknown> = {}
      // Only send what changed
      const current = configs.find((c) => c.id === id)
      if (editModel !== (current?.model ?? '')) payload.model = editModel || null
      if (editBaseUrl !== (current?.base_url ?? '')) payload.base_url = editBaseUrl || null
      if (editKey.trim()) payload.api_key = editKey.trim()
      await configApi.updateLlm(id, payload)
      setEditingId(null)
      setEditKey('')
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const activate = async (c: LlmConfig) => {
    if (c.is_active) return
    try {
      await configApi.updateLlm(c.id, { is_active: true })
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
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">LLM Config</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">Choose the model that writes your changelogs.</p>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelCls}>Provider</label>
            <ProviderDropdown
              value={provider}
              options={PROVIDERS}
              onChange={(id) => setProvider(id)}
            />
          </div>
          <div>
            <label className={labelCls}>
              API key {needsKey ? <span className="text-red-500">*</span> : <span className="text-zinc-400">(optional)</span>}
            </label>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              placeholder={needsKey ? 'Required' : 'Not required'} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Model <span className="text-zinc-400">(optional)</span></label>
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. gpt-4o-mini" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Base URL <span className="text-zinc-400">(optional)</span></label>
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…" className={inputCls} />
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button onClick={create} disabled={saving}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
          Save config
        </button>
      </div>

      <div className="space-y-2">
        {configs.length === 0 ? (
          <p className="rounded-xl border border-zinc-200 bg-white px-5 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            No configs yet — the built-in commit parser is used by default.
          </p>
        ) : (
          configs.map((c) => (
            <div key={c.id}
              className={`rounded-xl border bg-white dark:bg-zinc-900 ${editingId === c.id ? 'border-brand-300 dark:border-brand-700' : 'border-zinc-200 dark:border-zinc-800'}`}>
              <div className="flex items-center justify-between px-5 py-4">
              <div className="flex items-center gap-3">
                <BrandIcon provider={c.provider} size={18} />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize text-zinc-900 dark:text-zinc-50">{c.provider}</span>
                    {c.is_active
                      ? <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">active</span>
                      : <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">inactive</span>}
                  </div>
                  <p className="text-xs text-zinc-400">
                    {c.model || 'default model'}{c.has_api_key ? ' · key saved' : ' · no key'}
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
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">API key {c.has_api_key ? <span className="text-zinc-400">(leave blank to keep)</span> : <span className="text-brand-600">* required</span>}</label>
                      <input type="password" value={editKey} onChange={(e) => setEditKey(e.target.value)} placeholder={c.has_api_key ? '••••••••' : 'Paste API key'}
                        className={inputCls} />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Model</label>
                      <input value={editModel} onChange={(e) => setEditModel(e.target.value)} placeholder="e.g. openai/gpt-oss-120b" className={inputCls} />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Base URL</label>
                      <input value={editBaseUrl} onChange={(e) => setEditBaseUrl(e.target.value)} placeholder="https://…" className={inputCls} />
                    </div>
                  </div>
                  {c.provider !== 'commit' && !c.has_api_key && !editKey.trim() && (
                    <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">This provider needs an API key to generate.</p>
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
