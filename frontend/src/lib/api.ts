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
    // Expired/invalid session → clear it and go back to the login page,
    // instead of leaving the user on a screen where every call fails.
    if (res.status === 401 && !path.startsWith('/auth/')) {
      setToken(null)
      window.location.href = '/login'
    }
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
  generate: (body: { repo_id: string; from_tag?: string; to_tag?: string }) =>
    request<Changelog>('POST', '/changelogs/generate', body),
  list: (repoId?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams()
    if (repoId) params.set('repo_id', repoId)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return request<ChangelogListResponse>('GET', `/changelogs/?${params.toString()}`)
  },
  get: (id: string) => request<Changelog>('GET', `/changelogs/${id}`),
}

// Backend actions added for publishing
export interface PublishResult {
  /** "created" for a new release, "already_published" if it existed. */
  status: 'created' | 'already_published'
  tag?: string
  release_url?: string
  message?: string
}

export const publishApi = {
  publishRelease: (changelogId: string) =>
    request<PublishResult>('POST', `/changelogs/${changelogId}/publish-release`),
}

export const configApi = {
  listLlms: () => request<LlmConfig[]>('GET', '/changelogs/configs'),
  createLlm: (data: unknown) => request<LlmConfig>('POST', '/changelogs/configs', data),
  updateLlm: (id: string, data: unknown) =>
    request<LlmConfig>('PATCH', `/changelogs/configs/${id}`, data),
  removeLlm: (id: string) => request<void>('DELETE', `/changelogs/configs/${id}`),
}

export const notifyApi = {
  list: () => request<{ configs: NotifyConfig[] }>('GET', '/notify/configs'),
  create: (data: unknown) => request<NotifyConfig>('POST', '/notify/configs', data),
  update: (id: string, data: unknown) =>
    request<NotifyConfig>('PATCH', `/notify/configs/${id}`, data),
  remove: (id: string) => request<void>('DELETE', `/notify/configs/${id}`),
}