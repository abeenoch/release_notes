import { useEffect, useRef, useState } from 'react'

/**
 * Delete-style button with an in-app two-step confirmation — no native
 * browser dialog. First click arms it ("Sure?"); clicking again within
 * 3.5s confirms, otherwise it disarms back to idle.
 */
export function ConfirmButton({
  onConfirm,
  children,
  className = '',
  armedLabel = 'Sure?',
  confirmLabel = 'Yes, delete',
  title = 'Delete',
  disabled = false,
}: {
  onConfirm: () => void | Promise<void>
  children: React.ReactNode
  className?: string
  armedLabel?: string
  confirmLabel?: string
  title?: string
  disabled?: boolean
}) {
  const [armed, setArmed] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const click = async () => {
    if (!armed) {
      setArmed(true)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setArmed(false), 3500)
      return
    }
    if (timer.current) clearTimeout(timer.current)
    setArmed(false)
    await onConfirm()
  }

  if (armed) {
    return (
      <button
        onClick={click}
        onBlur={() => setArmed(false)}
        autoFocus
        disabled={disabled}
        className={`inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-red-700 disabled:opacity-50 ${className}`}
      >
        {confirmLabel}
      </button>
    )
  }

  return (
    <button
      onClick={click}
      title={title}
      aria-label={title}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-2 text-zinc-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-500/10 ${className}`}
    >
      {children}
      {armed && <span className="text-xs font-medium">{armedLabel}</span>}
    </button>
  )
}