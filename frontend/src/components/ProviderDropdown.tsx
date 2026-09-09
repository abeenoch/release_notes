import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { BrandIcon } from './BrandIcon'

export interface ProviderOption {
  id: string
  label: string
}

/**
 * Custom provider picker with brand icons, replacing the native <select>
 * (which loses styling/logos — especially on mobile's OS picker).
 */
export function ProviderDropdown({
  value,
  options,
  onChange,
  className = '',
}: {
  value: string
  options: ProviderOption[]
  onChange: (id: string) => void
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: Event) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('touchstart', onDoc)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('touchstart', onDoc)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  const selected = options.find((o) => o.id === value)

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`flex w-full items-center justify-between gap-2 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm ${className} dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100`}
      >
        <span className="flex min-w-0 items-center gap-2">
          <BrandIcon provider={selected?.id ?? value} size={18} />
          <span className="truncate">{selected?.label ?? value}</span>
        </span>
        <ChevronDown size={16} className={`shrink-0 text-zinc-400 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-40 mt-1 w-full overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-800 dark:shadow-zinc-900">
          {options.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                onChange(opt.id)
                setOpen(false)
              }}
              className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm ${
                opt.id === value
                  ? 'bg-brand-50 text-zinc-900 dark:bg-brand-500/10 dark:text-zinc-50'
                  : 'text-zinc-700 hover:bg-zinc-50 dark:text-zinc-200 dark:hover:bg-zinc-700/50'
              }`}
            >
              <BrandIcon provider={opt.id} size={18} />
              <span className="flex-1 text-left">{opt.label}</span>
              {opt.id === value && <span className="text-brand-600 text-xs font-semibold dark:text-brand-400">✓</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}