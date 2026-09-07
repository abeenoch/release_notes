import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, RefreshCw, Trash2, GitBranch, X } from 'lucide-react'
import { reposApi } from '../lib'
import type { Repository, GitHubRepo } from '../lib'

export function ReposPage() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [previewing, setPreviewing] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [candidates, setCandidates] = useState<GitHubRepo[]>([])
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState('')

  const load = useCallback(async () => {
    try {
      const r = await reposApi.list()
      setRepos(r.repos)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openPreview = async () => {
    setPreviewing(true)
    setImportError('')
    try {
      const res = await reposApi.preview()
      if (res.repos.length === 0) {
        alert('No repositories found on GitHub.')
        return
      }
      setCandidates(res.repos)
      setModalOpen(true)
    } catch (e) {
      alert(`Failed to fetch repos: ${(e as Error).message}`)
    } finally {
      setPreviewing(false)
    }
  }

  const importSelected = async (selected: string[]) => {
    setImporting(true)
    setImportError('')
    try {
      await reposApi.importRepos(selected)
      setModalOpen(false)
      await load()
    } catch (e) {
      setImportError((e as Error).message)
    } finally {
      setImporting(false)
    }
  }

  const remove = async (id: string) => {
    if (!confirm('Remove this repository from Release Notes?')) return
    await reposApi.remove(id)
    await load()
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="animate-spin text-zinc-400" size={24} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Repositories</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Sync from GitHub, then pick which repos get changelogs.
          </p>
        </div>
        <button
          onClick={openPreview}
          disabled={previewing}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          <RefreshCw size={16} className={previewing ? 'animate-pulse' : ''} />
          {previewing ? 'Fetching…' : 'Sync from GitHub'}
        </button>
      </div>

      {repos.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <GitBranch size={40} className="mx-auto mb-4 text-zinc-300 dark:text-zinc-600" />
          <h3 className="mb-1 text-base font-medium text-zinc-900 dark:text-zinc-50">No repositories</h3>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Sync from GitHub to import the ones you want.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {repos.map((repo) => (
            <div key={repo.id} className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900">
              <Link to={`/repos/${repo.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                  <GitBranch size={16} />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">{repo.full_name}</p>
                  <p className="text-xs text-zinc-400">
                    {repo.default_branch || 'main'} · {repo.is_private ? 'private' : 'public'}
                    {repo.is_active ? ' · active' : ''}
                  </p>
                </div>
              </Link>
              <button
                onClick={() => remove(repo.id)}
                className="rounded-lg p-2 text-zinc-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10"
                aria-label={`Remove ${repo.full_name}`}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <ImportModal
          candidates={candidates}
          importing={importing}
          error={importError}
          onImport={importSelected}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}

function ImportModal({
  candidates, importing, error, onImport, onClose,
}: {
  candidates: GitHubRepo[]
  importing: boolean
  error: string
  onImport: (names: string[]) => void
  onClose: () => void
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set())

  const toggle = (name: string) => {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const added = candidates.filter((r) => r.already_added)
  const fresh = candidates.filter((r) => !r.already_added)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6 font-sans">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-zinc-900">
        <div className="flex shrink-0 items-center justify-between border-b border-zinc-200 px-6 py-5 dark:border-zinc-800">
          <h2 className="m-0 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Import Repositories</h2>
          <button onClick={onClose} className="rounded p-1 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200" aria-label="Close">
            <X size={20} />
          </button>
        </div>
        <p className="shrink-0 border-b border-zinc-200 bg-zinc-50 px-6 py-2.5 text-[13px] text-zinc-500 dark:border-zinc-800 dark:bg-zinc-800/60 dark:text-zinc-400">
          Select repos to enable for changelog auto-generation.
        </p>
        <div className="flex-1 overflow-y-auto">
          {added.length > 0 && (
            <>
              <p className="px-6 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                Already imported ({added.length})
              </p>
              {added.map((r) => (
                <RepoRow key={r.full_name} repo={r} checked disabled />
              ))}
            </>
          )}
          {fresh.length > 0 && (
            <>
              <p className="px-6 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
                Available ({fresh.length})
              </p>
              {fresh.map((r) => (
                <RepoRow key={r.full_name} repo={r} checked={checked.has(r.full_name)} onToggle={() => toggle(r.full_name)} />
              ))}
            </>
          )}
        </div>
        <div className="flex shrink-0 items-center justify-between border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
          <span className="text-[13px] text-zinc-500 dark:text-zinc-400">{checked.size} selected</span>
          <button
            onClick={() => onImport(Array.from(checked))}
            disabled={importing || checked.size === 0}
            className="rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
          >
            {importing ? 'Importing…' : 'Import Selected'}
          </button>
        </div>
        {error && (
          <p className="px-6 pb-4 text-sm text-red-600 dark:text-red-400">{error}</p>
        )}
      </div>
    </div>
  )
}

function RepoRow({
  repo, checked, disabled, onToggle,
}: {
  repo: GitHubRepo
  checked: boolean
  disabled?: boolean
  onToggle?: () => void
}) {
  return (
    <div className="flex items-center gap-3 border-b border-zinc-100 px-6 py-2.5 dark:border-zinc-800">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={onToggle}
        className="h-[18px] w-[18px] accent-brand-600"
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">{repo.full_name}</p>
        <p className="truncate text-xs text-zinc-400">
          {repo.description || (repo.is_private ? 'Private repository' : 'Public repository')}
        </p>
      </div>
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        disabled ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400'
        : repo.is_private ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400'
        : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'
      }`}>
        {disabled ? 'Active' : repo.is_private ? 'Private' : 'Public'}
      </span>
    </div>
  )
}
