import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Logo from './Logo'

// The frame around every joiner and buddy page: a slim top bar and a centred column.
export default function EmployeeShell(props: {
  children: ReactNode
  portalLink?: boolean // the "My portal" link (not shown on the portal itself)
  plain?: boolean // no white card around the content (the portal draws its own cards)
  actions?: ReactNode // shown on the right of the top bar, e.g. Sign out
}) {
  const { children, portalLink = true, plain = false, actions } = props
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between gap-3 px-4">
          <Link to="/portal"><Logo /></Link>
          <div className="flex items-center gap-2">
            {portalLink && (
              <Link to="/portal" className="text-sm font-medium text-brand hover:text-brand-dark">My portal</Link>
            )}
            {actions}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-2xl px-4 py-6 sm:py-8">
        {plain ? children : (
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm sm:p-8">{children}</div>
        )}
      </main>
    </div>
  )
}
