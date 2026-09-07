import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Loader2, Sparkles, ArrowLeft, GitBranch } from 'lucide-react'
import { reposApi, changelogApi } from '../lib'
import { StatusBadge, RelativeDate } from '../components/StatusBadge'
import type { Changelog } from '../lib'

export function RepoDetailPage() {
  const { repoId } = useParams()
  const navigate = useNavigate()
  const [changelogs, setChangelogs] = useState<Changelog[]>([])
  const [repoName, setRepoName] = useState('')
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    if (!repoId) return
    try {
      const repos = (await reposApi.list()).repos
      setRepoName(repos.find((r) => r.id === repoId)?.full_name ?? 'Unknown')
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
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">{repoName}</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{changelogs.length} changelogs</p>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          <Sparkles size={16} className={generating ? 'animate-pulse' : ''} />
          {generating ? 'Queuing…' : 'Generate Now'}
        </button>
      </div>

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