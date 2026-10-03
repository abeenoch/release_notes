import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Loader2, FileText, Github } from 'lucide-react'
import { publicApi } from '../lib'
import { renderMarkdown } from '../lib/markdown'
import { RelativeDate } from '../components/StatusBadge'
import { SubscribeCard } from '../components/SubscribeCard'
import type { PublicPage as PublicPageData } from '../lib'

/**
 * Public vanity changelog page — the /owner/repo route, NO auth required.
 * Renders only what GET /public/{owner}/{repo} returns: completed
 * changelogs, no ids or internals.
 */
export function PublicChangelogPage() {
  const { owner, repo } = useParams()
  const [page, setPage] = useState<PublicPageData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!owner || !repo) return
    let cancelled = false
    publicApi
      .getPage(owner, repo)
      .then((p) => { if (!cancelled) setPage(p) })
      .catch(() => {
        if (!cancelled) setError('This changelog page does not exist or is not public.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [owner, repo])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Loader2 className="animate-spin text-zinc-400" size={24} />
      </div>
    )
  }

  if (error || !page) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 px-4 text-center dark:bg-zinc-950">
        <FileText size={40} className="text-zinc-300 dark:text-zinc-600" />
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Changelog not found</h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{error}</p>
        </div>
        <Link to="/" className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-400">
          Release Notes — go to app
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95" style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}>
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-3 py-3 sm:gap-4 sm:px-4 sm:py-5">
          <div className="min-w-0">
            <h1 className="text-base font-semibold break-words text-zinc-900 sm:text-xl dark:text-zinc-50">
              {page.full_name}
            </h1>
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
              {page.changelogs.length} {page.changelogs.length === 1 ? 'release' : 'releases'}
              {page.is_private && ' · private repository'}
            </p>
          </div>
          <Link
            to="/"
            className="shrink-0 rounded-lg px-3 py-2.5 text-sm font-medium text-brand-600 hover:underline dark:text-brand-400"
          >
            Release Notes
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl space-y-4 px-3 py-5 sm:space-y-6 sm:px-4 sm:py-8">
        <SubscribeCard owner={owner ?? ''} repo={repo ?? ''} />
        {page.changelogs.length === 0 ? (
          <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center sm:p-12 dark:border-zinc-800 dark:bg-zinc-900">
            <FileText size={36} className="mx-auto mb-3 text-zinc-300 dark:text-zinc-600" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No releases published yet.</p>
          </div>
        ) : (
          page.changelogs.map((c) => (
            <article
              key={`${c.version ?? 'v'}-${c.created_at}`}
              className="min-w-0 overflow-hidden rounded-xl border border-zinc-200 bg-white p-4 sm:p-6 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-2">
                <h2 className="min-w-0 text-base font-semibold break-words text-zinc-900 sm:text-lg dark:text-zinc-50">
                  {c.version || c.to_tag || 'Unversioned'}
                </h2>
                <span className="shrink-0 text-xs text-zinc-500 dark:text-zinc-400">
                  <RelativeDate date={c.created_at} />
                </span>
              </div>
              {c.summary && (
                <p className="mb-3 text-sm break-words text-zinc-600 sm:mb-4 dark:text-zinc-300">{c.summary}</p>
              )}
              <div className="markdown-body min-w-0" dangerouslySetInnerHTML={{ __html: renderMarkdown(c.raw_markdown || '') }} />
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-zinc-100 pt-3 text-xs text-zinc-400 sm:mt-4 dark:border-zinc-800">
                {c.commit_count != null && <span>{c.commit_count} commits</span>}
                {c.release_url && (
                  <a
                    href={c.release_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline dark:text-brand-400"
                  >
                    <Github size={12} /> View release
                  </a>
                )}
              </div>
            </article>
          ))
        )}
      </main>
    </div>
  )
}