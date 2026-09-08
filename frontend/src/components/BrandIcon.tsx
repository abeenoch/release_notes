import type { ComponentType } from 'react'
import { Mail, TerminalSquare } from 'lucide-react'
import { SiAnthropic, SiOpenrouter, SiOllama } from 'react-icons/si'

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyIcon = ComponentType<any>

interface BrandDef {
  /** Simple Icons glyph component (when the brand is published there) */
  glyph?: AnyIcon
  /** Brand color */
  color: string
  /** Hand-drawn inline SVG for brands Simple Icons no longer publishes */
  custom?: (size: number) => React.ReactNode
  /** Lucide fallback icon */
  lucide?: AnyIcon
}

/**
 * Product icons for integrations.
 * Anthropic / OpenRouter / Ollama come from Simple Icons; OpenAI, Groq,
 * Slack and SendGrid were removed from that set, so they get hand-drawn
 * marks that match each brand's look.
 */
export const BRAND_ICONS: Record<string, BrandDef> = {
  // ── LLM providers ──
  openai: {
    color: '#10a37f',
    custom: (s) => (
      <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
        {/* Hexagonal knot — stand-in for the OpenAI mark */}
        <path d="M12 2.5 20.3 7.3v9.4L12 21.5 3.7 16.7V7.3L12 2.5z" />
        <path d="M12 6.8 16.6 9.4v5.2L12 17.2l-4.6-2.6V9.4L12 6.8z" />
      </svg>
    ),
  },
  anthropic: { glyph: SiAnthropic, color: '#d97757' },
  groq: {
    color: '#f55036',
    custom: (s) => (
      <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        {/* Groq's angular bolt mark */}
        <path d="M13.6 2 4 13.2h5.2L9 22l10.4-11.4h-5.4L13.6 2z" />
      </svg>
    ),
  },
  openrouter: { glyph: SiOpenrouter, color: '#6566f1' },
  ollama: { glyph: SiOllama, color: '#0f0f0f' },
  commit: { lucide: TerminalSquare, color: '#71717a' },

  // ── Notification providers ──
  slack: {
    color: '#4a154b',
    custom: (s) => (
      <svg width={s} height={s} viewBox="0 0 24 24" aria-hidden="true">
        {/* Slack's four-lobe pinwheel */}
        <rect x="9.5" y="2" width="5" height="9" rx="2.5" fill="#36c5f0" />
        <rect x="13" y="9.5" width="9" height="5" rx="2.5" fill="#2eb67d" />
        <rect x="9.5" y="13" width="5" height="9" rx="2.5" fill="#ecb22e" />
        <rect x="2" y="9.5" width="9" height="5" rx="2.5" fill="#e01e5a" />
      </svg>
    ),
  },
  sendgrid: {
    color: '#1a82e2',
    custom: (s) => (
      <svg width={s} height={s} viewBox="0 0 24 24" aria-hidden="true">
        {/* SendGrid's pinwheel grid */}
        <rect x="2" y="2" width="7" height="7" fill="#991aec" />
        <rect x="9" y="9" width="7" height="7" fill="#3368fa" />
        <rect x="16" y="16" width="7" height="7" fill="#00a9d1" />
        <rect x="16" y="2" width="7" height="7" fill="#9dd6f9" />
        <rect x="2" y="16" width="7" height="7" fill="#9dd6f9" />
      </svg>
    ),
  },
  smtp: { lucide: Mail, color: '#ea580c' },
}

export function BrandIcon({
  provider,
  size = 18,
  className = '',
}: {
  provider: string
  size?: number
  className?: string
}) {
  const def = BRAND_ICONS[provider]
  if (!def) return null

  const glyph = def.custom
    ? def.custom(size)
    : def.glyph
      ? <def.glyph size={size} className={className} />
      : def.lucide
        ? <def.lucide size={size} className={className} />
        : null

  // Hand-drawn marks render in the brand colour on a neutral tile; glyph and
  // lucide icons render directly in the brand colour on a tinted background.
  const usesTile = !!def.custom

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-lg ${className}`}
      style={{
        width: size + 12,
        height: size + 12,
        background: usesTile
          ? 'rgba(0,0,0,0.045)'
          : `color-mix(in srgb, ${def.color} 12%, transparent)`,
        color: def.color,
      }}
      aria-label={provider}
      title={provider}
    >
      {glyph}
    </span>
  )
}