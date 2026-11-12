import { useCallback, useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  BarChart3, CalendarCheck, ChevronRight, HeartHandshake, LayoutDashboard, LogOut, Menu, ScrollText, Settings, UserPlus,
  UsersRound, X,
} from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import Logo from '../Logo'
import { logout, me } from './api'
import type { StaffUser } from './api'
import { BuddyPanel } from './BuddyGroups'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean }

// The everyday screens, then the set-up ones.
const MAIN: NavItem[] = [
  { to: '/hr', label: 'Home', icon: LayoutDashboard, end: true },
  { to: '/hr/joiners', label: 'Joiners', icon: UserPlus },
  { to: '/hr/buddies', label: 'Buddies', icon: HeartHandshake },
  { to: '/hr/induction', label: 'Induction', icon: CalendarCheck },
  { to: '/hr/clubs', label: 'Clubs', icon: UsersRound },
  { to: '/hr/reports', label: 'Reports', icon: BarChart3 },
]
const SETUP: NavItem[] = [
  { to: '/hr/settings', label: 'Settings', icon: Settings },
  { to: '/hr/audit', label: 'Audit log', icon: ScrollText },
]

/** What the admin pages get from the layout: bumps whenever the buddy panel changed a buddy. */
export type LayoutContext = { buddyChanged: number }

function Nav({ user, onNavigate, onSignOut }: { user: StaffUser; onNavigate: () => void; onSignOut: () => void }) {
  const item = (n: NavItem) => (
    <NavLink
      key={n.to}
      to={n.to}
      end={n.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `relative flex min-h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition ${
          isActive
            ? 'bg-brand-soft text-brand'
            : 'text-slate-600 hover:bg-slate-100 hover:text-ink'
        }`
      }
    >
      <n.icon size={18} aria-hidden />
      {n.label}
    </NavLink>
  )
  return (
    <div className="flex h-full flex-col">
      <nav className="flex-1 space-y-1 p-3" aria-label="Main">
        <div className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Programme</div>
        {MAIN.map(item)}
        <div className="px-3 pb-1 pt-6 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Setup</div>
        {SETUP.map(item)}
      </nav>
      <div className="border-t border-slate-200 p-3">
        <div className="flex items-center gap-3 rounded-md px-3 py-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
            {user.name.slice(0, 1).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-ink">{user.name}</span>
            <span className="block text-xs text-slate-500">Program admin</span>
          </span>
          <button
            type="button"
            onClick={onSignOut}
            className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-ink"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function HrLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [params, setParams] = useSearchParams()
  const [user, setUser] = useState<StaffUser | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [buddyChanged, setBuddyChanged] = useState(0)
  // Any page opens a buddy by adding ?buddy=<id> to its address (see useOpenBuddy). Back closes it.
  const openBuddy = Number(params.get('buddy')) || null

  useEffect(() => {
    me().then(setUser).catch(() => navigate('/login', { replace: true }))
  }, [navigate])

  const closeBuddy = useCallback(() => {
    setParams((prev) => {
      const p = new URLSearchParams(prev)
      p.delete('buddy')
      return p
    }, { replace: true })
  }, [setParams])

  if (!user) return <div className="p-10 text-center text-slate-500">Loading…</div>

  async function signOut() {
    await logout().catch(() => undefined)
    navigate('/login', { replace: true })
  }

  const current = [...MAIN, ...SETUP].find((n) => (n.end ? pathname === n.to : pathname.startsWith(n.to)))

  return (
    <div className="min-h-screen">
      {/* laptop: a fixed side menu */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <Link to="/hr" className="flex h-16 items-center border-b border-slate-200 px-5"><Logo /></Link>
        <Nav user={user} onNavigate={() => undefined} onSignOut={signOut} />
      </aside>

      {/* phone and tablet: a top bar, and the same menu sliding in from the left */}
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 lg:hidden">
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          className="-ml-2 rounded-md p-2 text-slate-600 hover:bg-slate-100"
          aria-label="Open menu"
        >
          <Menu size={22} />
        </button>
        <Link to="/hr"><Logo subtitle={false} /></Link>
        {current && <span className="ml-auto truncate text-sm font-medium text-slate-600">{current.label}</span>}
      </header>
      {menuOpen && (
        <div className="fixed inset-0 z-30 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setMenuOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col bg-white shadow-xl">
            <div className="flex h-14 items-center justify-between border-b border-slate-200 px-4">
              <Logo subtitle={false} />
              <button type="button" onClick={() => setMenuOpen(false)} className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-ink" aria-label="Close menu">
                <X size={20} />
              </button>
            </div>
            <Nav user={user} onNavigate={() => setMenuOpen(false)} onSignOut={signOut} />
          </div>
        </div>
      )}

      <main className="lg:pl-64">
        <div className="sticky top-0 z-10 hidden h-16 items-center justify-between border-b border-slate-200 bg-white px-8 lg:flex">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-400">COMPASS</span>
            <ChevronRight size={14} className="text-slate-300" aria-hidden />
            <span className="font-medium text-ink">{current?.label ?? 'Home'}</span>
          </div>
          <span className="text-sm text-slate-500">
            {new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </span>
        </div>
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet context={{ buddyChanged } satisfies LayoutContext} />
        </div>
      </main>
      {openBuddy && (
        <BuddyPanel key={openBuddy} id={openBuddy} onClose={closeBuddy} onChanged={() => setBuddyChanged((n) => n + 1)} />
      )}
    </div>
  )
}
