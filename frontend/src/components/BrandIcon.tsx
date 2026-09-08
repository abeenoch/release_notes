import type { ComponentType, ReactNode } from 'react'
import { Mail, TerminalSquare } from 'lucide-react'
import {
  OPENAI_PATH, ANTHROPIC_PATH, OPENROUTER_PATH,
  SLACK_PATH, SENDGRID_PATH,
} from './brandPaths'
import { OLLAMA_PATH } from './brandPaths.ollama'

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyIcon = ComponentType<any>

interface BrandDef {
  /** Official brand glyph (24×24 viewBox) */
  path?: string
  /** Brand color */
  color: string
  /** Custom mark for brands with no published glyph (Groq) */
  custom?: ReactNode
  /** Lucide fallback for generic providers */
  lucide?: AnyIcon
  /** Invert in dark mode (near-black brand colors) */
  invertInDark?: boolean
}

/**
 * Product icons for integrations, using each brand's real glyph:
 * Anthropic / OpenRouter / Ollama from the current Simple Icons set,
 * OpenAI / Slack / SendGrid from Simple Icons v13 (last release carrying
 * them), and a hand-drawn bolt for Groq (never published there).
 */
export const BRAND_ICONS: Record<string, BrandDef> = {
  openai: { color: '#10a37f', path: OPENAI_PATH },
  anthropic: { color: '#d97757', path: ANTHROPIC_PATH },
  groq: {
    color: '#f55036',
    custom: (
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M13.6 2 4 13.2h5.2L9 22l10.4-11.4h-5.4L13.6 2z" />
      </svg>
    ),
  },
  openrouter: { color: '#6566f1', path: OPENROUTER_PATH },
  ollama: { color: '#0f0f0f', path: OLLAMA_PATH, invertInDark: true },
  commit: { lucide: TerminalSquare, color: '#71717a' },

  slack: { color: '#4a154b', path: SLACK_PATH },
  sendgrid: { color: '#1a82e2', path: SENDGRID_PATH },
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

  let glyph: ReactNode
  if (def.custom) {
    glyph = (
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        {def.custom}
      </svg>
    )
  } else if (def.path) {
    glyph = (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d={def.path} />
      </svg>
    )
  } else if (def.lucide) {
    const L = def.lucide
    glyph = <L size={size} strokeWidth={1.8} />
  } else {
    return null
  }

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-lg ${className} ${
        def.invertInDark ? 'dark:invert' : ''
      }`}
      style={{
        width: size + 12,
        height: size + 12,
        color: def.color,
        background: `color-mix(in srgb, ${def.color} 12%, transparent)`,
      }}
      aria-label={provider}
      title={provider}
    >
      {glyph}
    </span>
  )
}