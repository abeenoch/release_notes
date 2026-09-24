import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Loader2, Sparkles, ArrowLeft, GitBranch } from 'lucide-react'
import { reposApi, changelogApi } from '../lib'
import { StatusBadge, RelativeDate } from '../components/StatusBadge'
import type { Changelog, Repository } from '../lib'

export function RepoDetailPage() {
  const { repoId } = useParams()
  const navigate = useNavigate()
  const [changelogs, setChangelogs] = useState<Changelog[]>([])
  const [repo, setRepo] = useState<Repository | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [rangeOpen, setRangeOpen] = useState(false)
  const [fromTag, setFromTag] = useState('')
  const [toTag, setToTag] = useState('')
  const [rangeError, setRangeError] = useState('')
  const [savingPublic, setSavingPublic] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    if (!repoId) return
    try {
      const repos = (await reposApi.list()).repos
      setRepo(repos.find((r) => r.id === repoId) ?? null)
      const res = await changelogApi.list(repoId)
      setChangelogs(res.changelogs)
      const busy = res.changelogs.some((c) => c.status === 'pending' || c.status === 'processing')
      if (!busy && pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }, [repoId])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 3000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [load])

  const generate = async () => {
    if (!repoId) return
    setGenerating(true)
    try {
      await changelogApi.generate({ repo_id: repoId })
      await load()
      pollRef.current = setInterval(load, 3000)
    } finally {
      setGenerating(false)
    }
  }

  const generateRange = async () => {
    if (!repoId) return
    const from = fromTag.trim()
    const to = toTag.trim()
    // Mirror the backend rule: both ends or neither — a partial range used
    // to be silently ignored and produced the wrong changelog.
    if (!from || !to) {
      setRangeError('Fill in both From and To — for the default range use Generate Now instead.')
      return
    }
    setGenerating(true)
    setRangeError('')
    try {
      await changelogApi.generate({ repo_id: repoId, from_tag: from, to_tag: to })
      setRangeOpen(false)
      setFromTag('')
      setToTag('')
      await load()
      pollRef.current = setInterval(load, 3000)
    } catch (e) {
      setRangeError((e as Error).message)
    } finally {
      setGenerating(false)
    }
  }

  const togglePublic = async () => {
    if (!repo) return
    setSavingPublic(true)
    try {
      const updated = await reposApi.setPublic(repo.id, !repo.public_enabled)
      setRepo({ ...repo, public_enabled: updated.public_enabled })
    } catch (e) {
      alert(`Could not update public page: ${(e as Error).message}`)
    } finally {
      setSavingPublic(false)
    }
  }

  const copyPublicLink = async () => {
    if (!repo) return
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/${repo.full_name}`)
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 1500)
    } catch {
      /* clipboard unavailable (http origin / denied) — link stays clickable */
    }
  }

  const embedSnippet = repo
    ? `<script src="${window.location.origin}/widget.js" data-repo="${repo.full_name}" async></script>`
    : ''

  const copyEmbed = async () => {
    try {
      await navigator.clipboard.writeText(embedSnippet)
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 1500)
    } catch {
      /* clipboard unavailable — snippet stays selectable */
    }
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
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/repos')}
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="break-words text-2xl font-semibold text-zinc-900 dark:text-zinc-50">{repo?.full_name ?? 'Unknown'}</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{changelogs.length} changelogs</p>
        </div>
        <button
          onClick={() => { setRangeOpen((v) => !v); setRangeError('') }}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          Range…
        </button>
        <button
          onClick={generate}
          disabled={generating}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          <Sparkles size={16} className={generating ? 'animate-pulse' : ''} />
          {generating ? 'Queuing…' : 'Generate Now'}
        </button>
      </div>

      {repo && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="min-w-0">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Public changelog page</p>
            <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
              {repo.public_enabled
                ? repo.is_private
                  ? 'ON — anyone with the link can read these changelogs, even though the repository is private.'
                  : 'ON — anyone with the link can read this repository’s completed changelogs.'
                : 'OFF — only you can see these changelogs.'}
            </p>
            {repo.public_enabled && (
              <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
                Confirmed subscribers get each release by email via your notification settings.
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">            {repo.public_enabled && (
              <>
                <a
                  href={`${window.location.origin}/${repo.full_name}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="max-w-[16rem] truncate rounded-lg bg-zinc-100 px-2.5 py-1.5 font-mono text-xs text-zinc-700 hover:text-brand-600 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  {window.location.origin}/{repo.full_name}
                </a>
                <button
                  onClick={copyPublicLink}
                  className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                >
                  {copiedLink ? 'Copied' : 'Copy'}
                </button>
              </>
            )}
            <button
              onClick={togglePublic}
              disabled={savingPublic}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 ${
                repo.public_enabled
                  ? 'border border-red-300 text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950'
                  : 'bg-brand-600 text-white hover:bg-brand-700'
              }`}
            >
              {savingPublic ? 'Saving…' : repo.public_enabled ? 'Disable' : 'Enable'}
            </button>
          </div>
        </div>
      )}

      {repo?.public_enabled && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-200 bg-white px-5 py-3 dark:border-zinc-800 dark:bg-zinc-900">
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Embed on your site:</span>
          <code className="min-w-0 flex-1 truncate rounded bg-zinc-100 px-2 py-1 font-mono text-[11px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
            {embedSnippet}
          </code>
          <button
            onClick={copyEmbed}
            className="rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            {copiedLink ? 'Copied' : 'Copy'}
          </button>
        </div>
      )}

      {rangeOpen && (
        <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-[10rem] flex-1">
              <span className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">From ref</span>
              <input
                value={fromTag}
                onChange={(e) => { setFromTag(e.target.value); setRangeError('') }}
                placeholder="v1.0.0 or commit"
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
              />
            </label>
            <label className="min-w-[10rem] flex-1">
              <span className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">To ref</span>
              <input
                value={toTag}
                onChange={(e) => { setToTag(e.target.value); setRangeError('') }}
                placeholder="v1.1.0 or commit"
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
              />
            </label>
            <button
              onClick={generateRange}
              disabled={generating}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
            >
              {generating ? 'Queuing…' : 'Generate range'}
            </button>
          </div>
          <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            Covers exactly From → To (e.g. <span className="font-mono">v1.0.0</span> → <span className="font-mono">v1.1.0</span>). Use Generate Now for the default incremental range.
          </p>
          {rangeError && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">{rangeError}</p>
          )}
        </div>
      )}

      {changelogs.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900">
          <GitBranch size={40} className="mx-auto mb-4 text-zinc-300 dark:text-zinc-600" />
          <h3 className="mb-1 text-base font-medium text-zinc-900 dark:text-zinc-50">No changelogs yet</h3>
          <p className="mb-4 text-sm text-zinc-500 dark:text-zinc-400">Generate your first changelog for this repository</p>
          <button
            onClick={generate}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            <Sparkles size={16} /> Generate Changelog
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {changelogs.map((c) => (
            <div
              key={c.id}
              onClick={() => c.status === 'completed' && navigate(`/changelogs/${c.id}`)}
              className={`flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-5 py-4 text-left transition-colors dark:border-zinc-800 dark:bg-zinc-900 ${
                c.status === 'completed' ? 'cursor-pointer hover:border-zinc-300 dark:hover:border-zinc-700' : 'opacity-70'
              }`}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    {c.version || c.to_tag || 'Unversioned'}
                  </p>
                  <StatusBadge status={c.status} notificationStatus={c.notification_status} />
                </div>
                <p className="mt-0.5 line-clamp-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {c.status === 'failed'
                    ? c.error_message || 'Generation failed'
                    : c.summary || (c.status === 'pending' ? 'Waiting to start…' : 'Processing…')}
                </p>
              </div>
              <div className="ml-4 flex shrink-0 items-center gap-3 text-xs text-zinc-400">
                {c.llm_provider && <span className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">{c.llm_provider}</span>}
                {c.commit_count != null && <span>{c.commit_count} commits</span>}
                <RelativeDate date={c.created_at} />
                {c.status === 'completed' && (
                  <Link to={`/changelogs/${c.id}`} className="font-medium text-brand-600 hover:underline dark:text-brand-400">
                    View
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}