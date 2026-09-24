import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Loader2, FileText, Github } from 'lucide-react'
import { publicApi } from '../lib'
import { renderMarkdown } from '../lib/markdown'
import { RelativeDate } from '../components/StatusBadge'
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
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-5">
          <div className="min-w-0">
            <h1 className="break-words text-xl font-semibold text-zinc-900 dark:text-zinc-50">
              {page.full_name}
            </h1>
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
              {page.changelogs.length} {page.changelogs.length === 1 ? 'release' : 'releases'}
              {page.is_private && ' · private repository'}
            </p>
          </div>
          <Link
            to="/"
            className="shrink-0 text-sm font-medium text-brand-600 hover:underline dark:text-brand-400"
          >
            Release Notes
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        {page.changelogs.length === 0 ? (
          <div className="rounded-xl border border-zinc-200 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900">
            <FileText size={36} className="mx-auto mb-3 text-zinc-300 dark:text-zinc-600" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No releases published yet.</p>
          </div>
        ) : (
          page.changelogs.map((c) => (
            <article
              key={`${c.version ?? 'v'}-${c.created_at}`}
              className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                  {c.version || c.to_tag || 'Unversioned'}
                </h2>
                <RelativeDate date={c.created_at} />
              </div>
              {c.summary && (
                <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-300">{c.summary}</p>
              )}
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(c.raw_markdown || '') }} />
              <div className="mt-4 flex items-center gap-4 border-t border-zinc-100 pt-3 text-xs text-zinc-400 dark:border-zinc-800">
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