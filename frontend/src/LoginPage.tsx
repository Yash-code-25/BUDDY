import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { CalendarCheck, HeartHandshake, MessageSquareHeart, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { demoSignIn, getDemoPeople, signIn } from './api'
import type { DemoPerson } from './api'
import { Notice } from './hr/ui'
import Logo from './Logo'
import { inputCls, primary } from './styles'
import { useSubmit } from './useSubmit'

const DEMO_SHOWN = 10 // per group; search to find anyone else

const POINTS = [
  { icon: HeartHandshake, text: 'Every new joiner is matched with a buddy who works the way they do.' },
  { icon: CalendarCheck, text: 'A clear 4-week induction, ticked off week by week.' },
  { icon: MessageSquareHeart, text: 'A quick review at the end keeps the matches getting better.' },
]

/** The one sign-in page. Program admins go to the admin screens, joiners and buddies to their portal. */
export default function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run } = useSubmit()
  // Filled only in development; in production the server answers 404 and the list never shows.
  const [demo, setDemo] = useState<DemoPerson[]>([])
  const [demoSearch, setDemoSearch] = useState('')
  const needle = demoSearch.trim().toLowerCase()
  const matches = (p: DemoPerson) =>
    !needle || `${p.name} ${p.username} ${p.detail}`.toLowerCase().includes(needle)

  useEffect(() => {
    getDemoPeople().then((d) => setDemo(d.people)).catch(() => setDemo([]))
  }, [])

  function go(signInCall: () => Promise<{ to: string }>) {
    return run(async () => navigate((await signInCall()).to, { replace: true }), 'Could not sign in.')
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    go(() => signIn(username, password))
  }

  return (
    <div className="flex min-h-screen">
      {/* laptop: the brand panel on the left */}
      <aside className="sticky top-0 hidden h-screen w-[44%] flex-col justify-between border-r border-slate-200 bg-brand-soft p-12 lg:flex">
        <Logo />
        <div>
          <h2 className="max-w-md text-3xl font-semibold leading-tight text-ink">Every new joiner deserves a great first month.</h2>
          <ul className="mt-8 space-y-5">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-slate-700">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white text-brand ring-1 ring-inset ring-slate-200"><Icon size={18} aria-hidden /></span>
                <span className="pt-1.5">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-slate-500">United Group · COMPASS buddy program</p>
      </aside>

      <main className="flex flex-1 flex-col bg-white items-center px-4 py-10 sm:px-6 lg:justify-center">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Admins, new joiners and buddies all sign in here.</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            {error && <Notice>{error}</Notice>}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="username">Username</label>
              <input id="username" className={inputCls} value={username} onChange={(e) => setUsername(e.target.value)}
                autoComplete="username" autoFocus />
              <p className="mt-1.5 text-xs text-slate-500">Joiners and buddies: the username in your COMPASS email.</p>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="password">Password</label>
              <input id="password" className={inputCls} type="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </div>
            <button type="submit" disabled={busy || !username || !password} className={`${primary} w-full`}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
            <p className="text-center text-xs text-slate-500">Lost your password? Ask the COMPASS team to email it to you again.</p>
          </form>

          {demo.length > 0 && (
            <section className="mt-10 border-t border-slate-200 pt-6">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Demo sign-in · development only</h2>
              <p className="mt-1 text-xs text-slate-500">Click a person to open their portal without a password.</p>
              <div className="relative mb-4 mt-3">
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
                <input
                  className={`${inputCls} pl-9`}
                  placeholder="Search by name, username, department or city"
                  aria-label="Search demo people"
                  value={demoSearch}
                  onChange={(e) => setDemoSearch(e.target.value)}
                />
              </div>
              {(['joiner', 'buddy'] as const).map((kind) => {
                const matching = demo.filter((p) => p.kind === kind && matches(p))
                const people = matching.slice(0, DEMO_SHOWN)
                if (people.length === 0) return null
                return (
                  <div key={kind} className="mb-4 last:mb-0">
                    <h3 className="mb-2 flex items-baseline justify-between text-xs font-semibold text-slate-600">
                      {kind === 'joiner' ? 'Joiners' : 'Buddies'}
                      <span className="font-normal text-slate-400">
                        {matching.length > DEMO_SHOWN ? `first ${DEMO_SHOWN} of ${matching.length}` : matching.length}
                      </span>
                    </h3>
                    <ul className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200 bg-white">
                      {people.map((p) => (
                        <li key={p.username}>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => go(() => demoSignIn(p.username, p.kind))}
                            className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition hover:bg-slate-50 disabled:opacity-40"
                          >
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-medium text-ink">{p.name}</span>
                              <span className="block truncate text-xs text-slate-500">{p.detail}</span>
                            </span>
                            <span className="shrink-0 rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">{p.username}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </section>
          )}
        </div>
      </main>
    </div>
  )
}
