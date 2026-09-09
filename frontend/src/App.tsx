import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  NavLink,
  useNavigate,
} from 'react-router-dom'
import { Settings, LayoutDashboard, GitBranch, Bell, LogOut, FileText } from 'lucide-react'
import { setToken, hasToken } from './lib'
import { ThemeToggle } from './components/ThemeToggle'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { ReposPage } from './pages/ReposPage'
import { RepoDetailPage } from './pages/RepoDetailPage'
import { ConfigPage } from './pages/ConfigPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { ChangelogDetailPage } from './pages/ChangelogDetailPage'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/repos', label: 'Repositories', icon: GitBranch },
  { to: '/config', label: 'LLM Config', icon: Settings },
  { to: '/notifications', label: 'Notifications', icon: Bell },
] as const

function SidebarLayout() {
  const navigate = useNavigate()

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
      isActive
        ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50'
        : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-200'
    }`

  const signOut = () => {
    setToken(null)
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row bg-zinc-50 dark:bg-zinc-950">
      {/* Desktop sidebar (hidden on mobile) */}
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="px-5 pb-5 pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
                <FileText size={18} className="text-white" />
              </div>
              <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
                Release Notes
              </span>
            </div>
            <ThemeToggle />
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'} className={linkClass}>
              <item.icon size={18} strokeWidth={1.5} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
          <button onClick={signOut} className={linkClass({ isActive: false })}>
            <LogOut size={18} strokeWidth={1.5} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-2 border-b border-zinc-200 bg-white px-3 py-2.5 md:hidden dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600">
            <FileText size={16} className="text-white" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            Release Notes
          </span>
        </div>
        <ThemeToggle />
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-4 pb-20 md:p-8">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around border-t border-zinc-200 bg-white/95 md:hidden dark:border-zinc-800 dark:bg-zinc-900/95"
        style={{ paddingBottom: 'max(0px, env(safe-area-inset-bottom))' }}
        aria-label="Navigation"
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${
                isActive
                  ? 'text-brand-600 dark:text-brand-400'
                  : 'text-zinc-500 dark:text-zinc-400'
              }`
            }
          >
            <item.icon size={20} strokeWidth={1.5} />
            {item.label.split(' ')[0]}
          </NavLink>
        ))}
        <button
          onClick={signOut}
          aria-label="Sign out"
          className="flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium text-zinc-500 dark:text-zinc-400"
        >
          <LogOut size={20} strokeWidth={1.5} />
          Sign out
        </button>
      </nav>
    </div>
  )
}

function RequireAuth() {
  if (!hasToken()) return <Navigate to="/login" replace />
  return <SidebarLayout />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route index element={<DashboardPage />} />
          <Route path="repos" element={<ReposPage />} />
          <Route path="repos/:repoId" element={<RepoDetailPage />} />
          <Route path="config" element={<ConfigPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="changelogs/:changelogId" element={<ChangelogDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}