export interface User {
  id: string
  github_username?: string | null
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
  last_generated_commit?: string | null
  created_at: string
  updated_at?: string | null
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
  created_at: string
}

export interface ChangelogListResponse {
  changelogs: Changelog[]
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
  smtp_secure?: boolean | null
  sendgrid_api_key?: string | null
  slack_webhook_url?: string | null
  slack_channel?: string | null
  from_email?: string | null
  to_email?: string | null
  subject_prefix?: string | null
  is_active: boolean
  created_at: string
}