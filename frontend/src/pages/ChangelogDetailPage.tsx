import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, Loader2, Copy, Check, Download, Github,
  FileUp, ExternalLink, AlertTriangle,
} from 'lucide-react'
import { changelogApi, publishApi } from '../lib'
import { StatusBadge, RelativeDate } from '../components/StatusBadge'
import type { Changelog } from '../lib'

function renderMarkdown(md: string): string {
  // Minimal, safe markdown → HTML (headings, lists, bold/italic, code, links)
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const inline = (s: string) =>
    esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')

  const lines = md.split('\n')
  const out: string[] = []
  let inList = false
  let inCode = false
  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCode) { out.push('</code></pre>'); inCode = false }
      else { if (inList) { out.push('</ul>'); inList = false } out.push('<pre><code>'); inCode = true }
      continue
    }
    if (inCode) { out.push(esc(line)); continue }
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) {
      if (inList) { out.push('</ul>'); inList = false }
      out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`)
      continue
    }
    const li = /^\s*[-*]\s+(.*)$/.exec(line)
    if (li) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push(`<li>${inline(li[1])}</li>`)
      continue
    }
    if (inList) { out.push('</ul>'); inList = false }
    if (/^\s*$/.test(line)) { out.push(''); continue }
    out.push(`<p>${inline(line)}</p>`)
  }
  if (inList) out.push('</ul>')
  if (inCode) out.push('</code></pre>')
  return out.join('\n')
}

export function ChangelogDetailPage() {
  const { changelogId } = useParams()
  const navigate = useNavigate()
  const [changelog, setChangelog] = useState<Changelog | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [releaseUrl, setReleaseUrl] = useState<string | null>(null)
  const [commitSha, setCommitSha] = useState<string | null>(null)
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

  useEffect(() => { load() }, [load])

  const copy = async () => {
    if (!changelog?.raw_markdown) return
    await navigator.clipboard.writeText(changelog.raw_markdown)
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
    try {
      const res = await publishApi.publishRelease(changelogId)
      if (res?.release_url) setReleaseUrl(res.release_url)
      await load()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setPublishing(false)
    }
  }

  const commitChangelogFile = async () => {
    if (!changelogId) return
    setCommitting(true)
    setActionError('')
    try {
      const res = await publishApi.commitChangelog(changelogId)
      if (res?.commit_sha) setCommitSha(res.commit_sha)
      await load()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setCommitting(false)
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
            <StatusBadge status={changelog.status} notificationStatus={changelog.notification_status} />
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
          <button onClick={publishRelease} disabled={publishing} className={`${btnBase} border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800`}>
            {publishing ? <Loader2 size={16} className="animate-spin" /> : <Github size={16} />}
            Publish as GitHub Release
          </button>
          <button onClick={commitChangelogFile} disabled={committing} className={`${btnBase} bg-brand-600 text-white hover:bg-brand-700`}>
            {committing ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
            Commit CHANGELOG.md
          </button>
          {releaseUrl && (
            <a href={releaseUrl} target="_blank" rel="noopener"
              className={`${btnBase} text-emerald-600 hover:underline dark:text-emerald-400`}>
              <ExternalLink size={16} /> View release
            </a>
          )}
        </div>
      )}

      {actionError && <p className="text-sm text-red-600 dark:text-red-400">{actionError}</p>}

      {commitSha && (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          CHANGELOG.md committed as <code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">{commitSha.slice(0, 7)}</code>
        </p>
      )}

      {isCompleted && changelog.raw_markdown && (
        <article className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(changelog.raw_markdown) }} />
        </article>
      )}
    </div>
  )
}