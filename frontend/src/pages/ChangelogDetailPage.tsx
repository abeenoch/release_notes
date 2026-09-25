import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, Loader2, Copy, Check, Download, Github,
  ExternalLink, AlertTriangle,
} from 'lucide-react'
import { changelogApi, publishApi } from '../lib'
import { renderMarkdown } from '../lib/markdown'
import { StatusBadge, RelativeDate } from '../components/StatusBadge'
import type { Changelog } from '../lib'

export function ChangelogDetailPage() {
  const { changelogId } = useParams()
  const navigate = useNavigate()
  const [changelog, setChangelog] = useState<Changelog | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishNote, setPublishNote] = useState('')
  const [actionError, setActionError] = useState('')

  const load = useCallback(async () => {
    if (!changelogId) return
    try {
      const c = await changelogApi.get(changelogId)
      setChangelog(c)
    } catch {
      setChangelog(null)
    } finally {
      setLoading(false)
    }
  }, [changelogId])

  // Re-run when the changelog settles, so polling stops at a terminal state.
  const settled = changelog?.status === 'completed' || changelog?.status === 'failed'

  // Publishing is create-once: derive it from the changelog, not from the last
  // response, so the "already published" state survives a reload.
  const published = !!changelog?.release_url
  const releaseUrl = changelog?.release_url ?? null

  useEffect(() => {
    if (settled) return
    load()
    const id = setInterval(() => {
      if (document.visibilityState !== 'visible') return
      load()
    }, 3000)
    return () => clearInterval(id)
  }, [load, settled])

  const copy = async () => {
    if (!changelog?.raw_markdown) return
    try {
      await navigator.clipboard.writeText(changelog.raw_markdown)
    } catch {
      // Fallback for older browsers / insecure context
      const ta = document.createElement('textarea')
      ta.value = changelog.raw_markdown
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const download = () => {
    if (!changelog?.raw_markdown) return
    const blob = new Blob([changelog.raw_markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${changelog.version || changelog.to_tag || 'changelog'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const publishRelease = async () => {
    if (!changelogId) return
    setPublishing(true)
    setActionError('')
    setPublishNote('')
    try {
      const res = await publishApi.publishRelease(changelogId)
      // Publishing is create-once: a second click is not an error, it just
      // reports that the notes are already live.
      if (res?.status === 'already_published') {
        setPublishNote(res.message || 'The release notes for this changelog have already been published')
      }
      await load()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setPublishing(false)
    }
  }


  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="animate-spin text-zinc-400" size={24} />
      </div>
    )
  }

  if (!changelog) {
    return (
      <div className="space-y-4">
        <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200">
          <ArrowLeft size={16} /> Back
        </button>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Changelog not found.</p>
      </div>
    )
  }

  const version = changelog.version || changelog.to_tag || 'Unversioned'
  const isCompleted = changelog.status === 'completed'
  const btnBase = 'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed'

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)}
          className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">{version}</h1>
            <StatusBadge status={changelog.status} />
          </div>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            {changelog.from_tag ? `${changelog.from_tag} → ` : ''}
            {changelog.to_tag || 'HEAD'}
            {changelog.commit_count != null && ` · ${changelog.commit_count} commits`}
            {' · '}
            <RelativeDate date={changelog.created_at} />
            {changelog.llm_provider && ` · ${changelog.llm_provider}`}
          </p>
        </div>
      </div>

      {changelog.status === 'failed' && changelog.error_message && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-500/30 dark:bg-red-500/10">
          <AlertTriangle size={18} className="mt-0.5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-700 dark:text-red-300">Generation failed</p>
            <p className="mt-0.5 text-sm text-red-600 dark:text-red-400">{changelog.error_message}</p>
          </div>
        </div>
      )}

      {isCompleted && (
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={copy} className={`${btnBase} border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800`}>
            {copied ? <Check size={16} className="text-emerald-500" /> : <Copy size={16} />}
            {copied ? 'Copied' : 'Copy markdown'}
          </button>
          <button onClick={download} className={`${btnBase} border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800`}>
            <Download size={16} /> Download .md
          </button>
          {published ? (
            // Already published: don't invite a pointless second click.
            <span className={`${btnBase} border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400`}>
              <Check size={16} />
              Published
              {changelog.published_at && (
                <span className="font-normal opacity-80">· {new Date(changelog.published_at).toLocaleDateString()}</span>
              )}
            </span>
          ) : (
            <button onClick={publishRelease} disabled={publishing} className={`${btnBase} border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800`}>
              {publishing ? <Loader2 size={16} className="animate-spin" /> : <Github size={16} />}
              Publish as GitHub Release
            </button>
          )}
          {releaseUrl && (
            <a href={releaseUrl} target="_blank" rel="noopener"
              className={`${btnBase} text-emerald-600 hover:underline dark:text-emerald-400`}>
              <ExternalLink size={16} /> View release
            </a>
          )}
        </div>
      )}

      {publishNote && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
          {publishNote}
        </p>
      )}

      {actionError && <p className="text-sm text-red-600 dark:text-red-400">{actionError}</p>}

      {isCompleted && changelog.raw_markdown && (
        <article className="overflow-x-auto rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:p-6">
          <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(changelog.raw_markdown) }} />
        </article>
      )}
    </div>
  )
}