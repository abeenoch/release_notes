export interface User {
  id: string
  github_login?: string | null
  /** @deprecated alias kept for older call sites */
  github_username?: string | null
  display_name?: string | null
  avatar_url?: string | null
  email?: string | null
}

export interface Repository {
  id: string
  user_id: string
  github_repo_id?: number | null
  full_name: string
  clone_url?: string | null
  default_branch?: string | null
  is_active: boolean
  is_private?: boolean | null
  /** Public vanity page (/owner/repo) — strictly opt-in, off by default. */
  public_enabled?: boolean | null
  last_generated_commit?: string | null
  created_at: string
  updated_at?: string | null
}

/** One completed changelog on a public page — no ids, no internals. */
export interface PublicChangelog {
  version: string | null
  previous_version?: string | null
  from_tag?: string | null
  to_tag?: string | null
  summary?: string | null
  raw_markdown?: string | null
  commit_count?: number | null
  release_url?: string | null
  published_at?: string | null
  created_at: string
}

export interface PublicPage {
  full_name: string
  is_private: boolean
  changelogs: PublicChangelog[]
}

export interface SubscribeResult {
  status: 'pending_confirmation' | 'already_subscribed'
  message: string
}

export interface TokenActionResult {
  status: 'confirmed' | 'unsubscribed' | 'not_found'
  message: string
}

export type ChangelogStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type NotificationStatus = 'sent' | 'skipped' | 'failed' | null

export interface Changelog {
  id: string
  repo_id: string
  from_tag?: string | null
  to_tag?: string | null
  version?: string | null
  previous_version?: string | null
  summary?: string | null
  raw_markdown?: string | null
  llm_provider?: string | null
  commit_count?: number | null
  status: ChangelogStatus
  error_message?: string | null
  notification_status?: NotificationStatus
  /** Set once the notes have been published as a GitHub Release. */
  release_url?: string | null
  published_at?: string | null
  created_at: string
}

export interface ChangelogListResponse {
  changelogs: Changelog[]
  /** Full count ignoring limit/offset — stats read this, not the page length. */
  total: number
}

export interface LlmConfig {
  id: string
  provider: string
  model?: string | null
  base_url?: string | null
  is_active: boolean
  has_api_key: boolean
  created_at: string
}

export interface NotifyConfig {
  id: string
  provider: string
  smtp_host?: string | null
  smtp_port?: number | null
  smtp_user?: string | null
  has_smtp_pass?: boolean
  smtp_secure?: boolean | null
  has_sendgrid_key?: boolean
  sendgrid_api_key?: string | null
  slack_webhook_url?: string | null
  slack_channel?: string | null
  from_email?: string | null
  to_email?: string | null
  subject_prefix?: string | null
  is_active: boolean
  created_at: string
}