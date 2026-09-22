import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitBranch, FileText, Settings, Loader2 } from 'lucide-react'
import { authApi, reposApi, changelogApi, configApi } from '../lib'
import { StatusBadge, RelativeDate } from '../components/StatusBadge'
import type { Changelog, Repository } from '../lib'

const POLL_MS = 5000

export function DashboardPage() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [changelogs, setChangelogs] = useState<Changelog[]>([])
  // Full totals from /stats/summary — the list endpoint is paginated, so the
  // page length must never stand in for the real count.
  const [totalChangelogs, setTotalChangelogs] = useState<number | null>(null)
  const [publishedCount, setPublishedCount] = useState<number | null>(null)
  const [hasLlm, setHasLlm] = useState(false)
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    try {
      const [_, r, c, l, s] = await Promise.all([
        authApi.me().catch(() => null),
        reposApi.list().catch(() => ({ repos: [] })),
        changelogApi.list().catch(() => ({ changelogs: [] })),
        configApi.listLlms().catch(() => []),
        changelogApi.stats().catch(() => null),
      ])
      setRepos(r?.repos ?? [])
      setChangelogs(c?.changelogs ?? [])
      setHasLlm((l ?? []).some((x) => x.is_active))
      if (s) {
        setTotalChangelogs(s.changelogs_total)
        setPublishedCount(s.changelogs_published)
      }
    } catch {
      /* keep last good state on transient failures */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // Live updates: a webhook-created changelog appears without reload.
    // Polling is cheap (one small JSON list) and pauses when tab hidden.
    const tick = () => {
      if (document.visibilityState !== 'visible') return
      load()
    }
    pollRef.current = setInterval(tick, POLL_MS)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [load])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="animate-spin text-zinc-400" size={24} />
      </div>
    )
  }

  const activeRepos = repos.filter((r) => r.is_active)
  const stats = [
    { label: 'Repositories', value: activeRepos.length, icon: GitBranch },
    { label: 'Changelogs', value: totalChangelogs ?? changelogs.length, icon: FileText },
    { label: 'LLM Connected', value: hasLlm ? 'Yes' : 'No', icon: Settings },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Dashboard</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">Overview of your repos and recent releases.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <s.icon size={18} />
              </div>
              <div>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{s.label}</p>
                <p className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{s.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <h2 className="font-medium text-zinc-900 dark:text-zinc-50">Recent changelogs</h2>
          <div className="flex items-center gap-3 text-sm">
            {publishedCount != null && publishedCount > 0 && (
              <span className="text-zinc-500 dark:text-zinc-400">{publishedCount} published</span>
            )}
            <Link to="/repos" className="text-brand-600 hover:underline dark:text-brand-400">View repos</Link>
          </div>
        </div>
        {changelogs.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">No changelogs yet.</p>
        ) : (
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {changelogs.slice(0, 5).map((c) => (
              <div key={c.id} className="flex items-center justify-between px-5 py-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
                      {c.version || c.to_tag || 'Unversioned'}
                    </p>
                    <StatusBadge status={c.status} notificationStatus={c.notification_status} />
                  </div>
                  <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">{c.summary || ''}</p>
                </div>
                <div className="ml-4 flex shrink-0 items-center gap-3 text-xs text-zinc-400">
                  {c.repo_id && <RelativeDate date={c.created_at} />}
                  {c.status === 'completed' && (
                    <Link to={`/changelogs/${c.id}`} className="text-brand-600 hover:underline dark:text-brand-400">
                      View
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}