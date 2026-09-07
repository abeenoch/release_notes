import { Check, Clock, Loader2, X } from 'lucide-react'
import type { ChangelogStatus, NotificationStatus } from '../lib'

export function StatusBadge({
  status,
  notificationStatus,
}: {
  status: ChangelogStatus
  notificationStatus?: NotificationStatus
}) {
  if (status === 'pending' || status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-600 dark:bg-amber-500/10 dark:text-amber-400">
        <Loader2 size={12} className="animate-spin" />
        {status === 'processing' ? 'Generating...' : 'Queued'}
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-red-50 px-2 py-0.5 text-xs font-medium text-red-600 dark:bg-red-500/10 dark:text-red-400">
        <X size={12} />
        Failed
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
      <Check size={12} />
      Done
      {notificationStatus === 'sent' && <Check size={12} className="text-emerald-500" />}
    </span>
  )
}

export function RelativeDate({ date }: { date: string }) {
  const then = new Date(date).getTime()
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000))
  const label =
    mins < 1 ? 'just now'
    : mins < 60 ? `${mins}m ago`
    : mins < 1440 ? `${Math.round(mins / 60)}h ago`
    : `${Math.round(mins / 1440)}d ago`
  return <span title={new Date(date).toLocaleString()}>{label}</span>
}

export { Clock }