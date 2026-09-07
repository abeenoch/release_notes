import { useEffect, useState } from 'react'
import { Loader2, Trash2, Check } from 'lucide-react'
import { configApi } from '../lib'
import type { LlmConfig } from '../lib'

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
    if (!confirm('Delete this LLM config?')) return
    await configApi.removeLlm(id)
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
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">LLM Config</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">Choose the model that writes your changelogs.</p>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelCls}>Provider</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} className={inputCls}>
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
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
            <div key={c.id} className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center gap-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${c.is_active ? 'bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400' : 'bg-zinc-50 text-zinc-400 dark:bg-zinc-800'}`}>
                  <Check size={16} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize text-zinc-900 dark:text-zinc-50">{c.provider}</span>
                    {c.is_active && <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">active</span>}
                  </div>
                  <p className="text-xs text-zinc-400">
                    {c.model || 'default model'}{c.has_api_key ? ' · key saved' : ''}
                  </p>
                </div>
              </div>
              <button onClick={() => remove(c.id)}
                className="rounded-lg p-2 text-zinc-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10">
                <Trash2 size={16} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
