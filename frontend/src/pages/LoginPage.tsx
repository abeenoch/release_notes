import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText } from 'lucide-react'
import { authApi, setToken } from '../lib'
import { ThemeToggle } from '../components/ThemeToggle'

const CLIENT_ID = 'Ov23ligbTLjZzb1vZuMr'
const SCOPES = 'repo,user:email'

function startOAuth() {
  const redirectUri = window.location.origin + '/'
  window.location.href =
    'https://github.com/login/oauth/authorize'
    + `?client_id=${encodeURIComponent(CLIENT_ID)}`
    + `&redirect_uri=${encodeURIComponent(redirectUri)}`
    + `&scope=${encodeURIComponent(SCOPES)}`
}

export function LoginPage() {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    if (!code) return
    setBusy(true)
    authApi
      .loginWithGitHub(code)
      .then(({ access_token }) => {
        setToken(access_token)
        window.history.replaceState({}, '', '/')
        navigate('/repos', { replace: true })
      })
      .catch((err) => {
        alert(`Sign-in failed: ${err.message}`)
        window.history.replaceState({}, '', '/')
      })
      .finally(() => setBusy(false))
  }, [navigate])

  return (
    <div className="flex min-h-screen bg-white dark:bg-zinc-950">
      <div className="flex flex-1 flex-col justify-center px-6 py-10 md:px-16">
        <div className="pb-10">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600">
              <FileText size={22} className="text-white" />
            </div>
            <span className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Release Notes</span>
          </div>
          <h1 className="mb-3 text-2xl font-semibold tracking-tight text-zinc-900 sm:text-4xl dark:text-zinc-50">
            Changelogs that write themselves.
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400">
            Connect GitHub, pick your repos, and get AI-crafted release notes on every push.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={startOAuth}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.33-1.28-1.68-1.28-1.68-1.04-.72.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.7 1.25 3.35.96.1-.75.4-1.25.72-1.54-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.19a11.04 11.04 0 0 1 5.8 0c2.2-1.5 3.17-1.19 3.17-1.19.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.41-5.25 5.69.41.36.78 1.06.78 2.14 0 1.54-.01 2.79-.01 3.17 0 .31.2.68.8.56A11.51 11.51 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5z"/></svg>
            {busy ? 'Signing in…' : 'Sign in with GitHub'}
          </button>
          <ThemeToggle />
        </div>
      </div>
      <div className="hidden flex-1 items-center justify-center bg-gradient-to-br from-brand-600/10 via-transparent to-brand-500/10 lg:flex">
        <div className="max-w-sm text-center">
          <FileText size={48} className="mx-auto mb-4 text-brand-600" />
          <p className="text-lg font-medium text-zinc-900 dark:text-zinc-100">
            Forge clarity from every commit
          </p>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Incremental, AI-generated changelogs delivered automatically.
          </p>
        </div>
      </div>
    </div>
  )
}