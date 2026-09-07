const BASE = '/api'

import type {
  User, Repository, Changelog, ChangelogListResponse,
  LlmConfig, NotifyConfig, ChangelogStatus, NotificationStatus,
} from './types'

export type { User, Repository, Changelog, ChangelogListResponse, LlmConfig, NotifyConfig, ChangelogStatus, NotificationStatus }

function getToken(): string | null {
  return localStorage.getItem('arn_token')
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem('arn_token', token)
  else localStorage.removeItem('arn_token')
}

export function hasToken(): boolean {
  return !!getToken()
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error((data?.detail as string) || data?.message || 'Request failed')
  }
  return data as T
}

export const authApi = {
  loginWithGitHub: (code: string) =>
    request<{ access_token: string }>('POST', '/auth/github', { code }),
  me: () => request<User>('GET', '/auth/me'),
}

export interface GitHubRepo {
  full_name: string
  default_branch: string
  is_private: boolean
  description?: string | null
  already_added: boolean
}

export const reposApi = {
  list: () => request<{ repos: Repository[] }>('GET', '/repos/'),
  preview: () => request<{ repos: GitHubRepo[] }>('POST', '/repos/preview'),
  importRepos: (fullNames: string[]) =>
    request<{ repos: Repository[] }>('POST', '/repos/import', { full_names: fullNames }),
  remove: (id: string) => request<void>('DELETE', `/repos/${id}`),
}

export const changelogApi = {
  generate: (body: { repo_id: string }) =>
    request<Changelog>('POST', '/changelogs/generate', body),
  list: (repoId?: string) =>
    request<ChangelogListResponse>('GET', `/changelogs/${repoId ? `?repo_id=${repoId}` : ''}`),
  get: (id: string) => request<Changelog>('GET', `/changelogs/${id}`),
}

// Backend actions added for publishing + changelog maintenance
export const publishApi = {
  publishRelease: (changelogId: string) =>
    request<{ release_url?: string; tag?: string }>(
      'POST', `/changelogs/${changelogId}/publish-release`),
  commitChangelog: (changelogId: string) =>
    request<{ commit_sha?: string; branch?: string; file?: string }>(
      'POST', `/changelogs/${changelogId}/commit-changelog`),
}

export const configApi = {
  listLlms: () => request<LlmConfig[]>('GET', '/changelogs/configs'),
  createLlm: (data: unknown) => request<LlmConfig>('POST', '/changelogs/configs', data),
  removeLlm: (id: string) => request<void>('DELETE', `/changelogs/configs/${id}`),
}

export const notifyApi = {
  list: () => request<{ configs: NotifyConfig[] }>('GET', '/notify/configs'),
  create: (data: unknown) => request<NotifyConfig>('POST', '/notify/configs', data),
  remove: (id: string) => request<void>('DELETE', `/notify/configs/${id}`),
}