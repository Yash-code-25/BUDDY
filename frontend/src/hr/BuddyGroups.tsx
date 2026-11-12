import { ChevronRight } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api'
import { buddyAction, getBuddy } from './api'
import type { BuddyDetail, BuddyGroup } from './api'
import { PAIRING_OUTCOME, POOL_TONE, pairingDates, useActions } from './helpers'
import { AnswerTiles, Badge, Notice } from './ui'
import { primary, secondary } from '../styles'

type GroupBuddy = BuddyGroup['buddies'][number]

const groupKey = (g: BuddyGroup) => `${g.department}|${g.location}`
const groupId = (g: BuddyGroup) => `group-${groupKey(g).replace(/[^a-zA-Z0-9]+/g, '-')}`

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

function Avatar({ name, large }: { name: string; large?: boolean }) {
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full bg-brand-soft font-semibold text-brand ${
        large ? 'h-12 w-12 text-base' : 'h-10 w-10 text-sm'
      }`}
    >
      {initials(name)}
    </span>
  )
}

/** A buddy who is active, has finished their profile and looks after nobody can take a joiner now. */
const isFree = (b: GroupBuddy) =>
  b.pool_status === 'ACTIVE' && b.cmpbd_status === 'completed' && b.joiners.length === 0

function Stat({ children, tone = 'slate' }: { children: ReactNode; tone?: 'slate' | 'amber' | 'green' }) {
  const tones = { slate: 'bg-slate-100 text-slate-700', amber: 'bg-amber-100 text-amber-800', green: 'bg-success-soft text-success' }
  return <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${tones[tone]}`}>{children}</span>
}

function BuddyCard({ b, onOpen }: { b: GroupBuddy; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex h-full w-full flex-col rounded-lg border border-slate-200 bg-white p-4 text-left transition hover:border-brand/40 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      <div className="flex items-start gap-3">
        <Avatar name={b.name} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-brand">{b.name}</div>
          <div className="truncate text-xs text-slate-500">{b.designation || b.employee_id}</div>
        </div>
        <Badge tone={POOL_TONE[b.pool_status] ?? 'slate'}>{b.pool_status_label}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {b.cmpbd_status !== 'completed' && <Badge tone="amber">Profile pending</Badge>}
        {b.joiners.map((j) => (
          <span
            key={j.joiner_id}
            className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-1 text-xs font-medium text-success"
          >
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
            <span className="truncate">{j.name}</span>
          </span>
        ))}
        {b.joiners.length === 0 && b.cmpbd_status === 'completed' && (
          <span className="text-xs text-slate-400">{isFree(b) ? 'Free to take a joiner' : 'No joiners right now'}</span>
        )}
      </div>

      <div className="mt-auto flex items-center justify-between pt-3 text-xs text-slate-500">
        <span>{b.active_joiners} active · {b.total_joiners} in total</span>
        <span className="font-medium text-brand">View bonds →</span>
      </div>
    </button>
  )
}

/** Buddies laid out in groups (department and location), as cards. Clicking a card opens the buddy. */
export function BuddyGroupsView({ groups, onOpen }: { groups: BuddyGroup[]; onOpen: (id: number) => void }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const allCollapsed = collapsed.size === groups.length

  function toggle(key: string) {
    const next = new Set(collapsed)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setCollapsed(next)
  }

  function jump(g: BuddyGroup) {
    if (collapsed.has(groupKey(g))) toggle(groupKey(g))
    document.getElementById(groupId(g))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (groups.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
        No buddies match these filters.
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <nav aria-label="Jump to a group" className="-mx-1 flex flex-1 gap-2 overflow-x-auto px-1 py-0.5 [scrollbar-width:none]">
          {groups.map((g) => (
            <button
              key={groupKey(g)}
              type="button"
              onClick={() => jump(g)}
              className="inline-flex min-h-9 shrink-0 items-center gap-2 rounded-full border border-slate-300 bg-white px-3 text-sm text-slate-700 hover:border-brand/50"
            >
              {g.department} · {g.location}
              <span className="rounded-full bg-slate-100 px-1.5 text-xs font-medium text-slate-600">{g.buddies.length}</span>
            </button>
          ))}
        </nav>
        <button
          type="button"
          className="min-h-9 shrink-0 text-sm font-medium text-brand hover:underline"
          onClick={() => setCollapsed(allCollapsed ? new Set() : new Set(groups.map(groupKey)))}
        >
          {allCollapsed ? 'Expand all' : 'Collapse all'}
        </button>
      </div>

      <div className="space-y-4">
        {groups.map((g) => {
          const key = groupKey(g)
          const open = !collapsed.has(key)
          const free = g.buddies.filter(isFree).length
          return (
            <section key={key} id={groupId(g)} className="scroll-mt-4 rounded-lg border border-slate-200 bg-slate-50/60">
              <button
                type="button"
                aria-expanded={open}
                onClick={() => toggle(key)}
                className="flex w-full flex-wrap items-center justify-between gap-3 rounded-lg bg-white p-4 text-left"
              >
                <span className="flex items-center gap-3">
                  <ChevronRight size={18} aria-hidden className={`shrink-0 text-slate-400 transition-transform ${open ? 'rotate-90' : ''}`} />
                  <span>
                    <span className="block text-xs font-medium uppercase tracking-wide text-success">Buddy group</span>
                    <span className="block text-lg font-semibold text-ink">{g.department} · {g.location}</span>
                  </span>
                </span>
                <span className="flex flex-wrap gap-1.5">
                  <Stat>{g.buddies.length} {g.buddies.length === 1 ? 'buddy' : 'buddies'}</Stat>
                  <Stat>{g.active_joiners} active {g.active_joiners === 1 ? 'joiner' : 'joiners'}</Stat>
                  {free > 0 && <Stat tone="green">{free} free</Stat>}
                </span>
              </button>
              {open && (
                <div className="grid gap-3 p-3 sm:grid-cols-2 sm:p-4 xl:grid-cols-3">
                  {g.buddies.map((b) => (
                    <BuddyCard key={b.id} b={b} onOpen={() => onOpen(b.id)} />
                  ))}
                </div>
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}

// ---------- the side panel: one buddy and their bonds ----------

type Pairing = BuddyDetail['history'][number]

const isCurrent = (p: Pairing) => p.status === 'ACTIVE'


/** Opens from the right on a computer and fills the screen on a phone. Esc or the backdrop closes it. */
export function BuddyPanel({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const [buddy, setBuddy] = useState<BuddyDetail | null>(null)
  const { error, setError, message, act: run } = useActions()
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    let cancelled = false
    getBuddy(id)
      .then((b) => !cancelled && setBuddy(b))
      .catch((e) => !cancelled && setError(errorMessage(e, 'Could not load this buddy.')))
    return () => {
      cancelled = true
    }
  }, [id, setError])

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden' // the page behind does not scroll while the panel is open
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
    }
  }, [onClose])

  const act = (action: string, done: string) =>
    run(async () => {
      await buddyAction(id, action)
      setBuddy(await getBuddy(id))
      onChanged()
    }, done)

  const current = buddy?.history.filter(isCurrent) ?? []
  const past = buddy?.history.filter((p) => !isCurrent(p)) ?? []
  const completed = buddy?.cmpbd_status === 'completed'

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={buddy ? `${buddy.name}, buddy` : 'Buddy'}
        className="flex h-full w-full flex-col bg-white shadow-xl sm:max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 border-b border-slate-200 p-4 sm:p-5">
          {buddy ? (
            <>
              <Avatar name={buddy.name} large />
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold text-ink">{buddy.name}</h2>
                <div className="truncate text-sm text-slate-500">
                  {[buddy.designation, buddy.department, buddy.location].filter(Boolean).join(' · ')}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone={POOL_TONE[buddy.pool_status] ?? 'slate'}>{buddy.pool_status_label}</Badge>
                  {!completed && <Badge tone="amber">Profile pending</Badge>}
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 text-slate-500">{error ? '' : 'Loading…'}</div>
          )}
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xl text-slate-500 hover:bg-slate-100"
          >
            ×
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-5">
          {error && <Notice>{error}</Notice>}
          {message && <Notice kind="ok">{message}</Notice>}

          {buddy && (
            <>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ['Joiners now', buddy.active_joiners],
                  ['Joiners in total', buddy.total_joiners],
                  ['In pool since', buddy.date_added
                    ? new Date(buddy.date_added).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
                    : '-'],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3">
                    <div className="text-lg font-semibold text-ink">{value}</div>
                    <div className="text-xs text-slate-500">{label}</div>
                  </div>
                ))}
              </div>

              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">Looking after now</h3>
                {current.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-300 px-4 py-3 text-sm text-slate-500">
                    No joiners right now.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {current.map((p) => (
                      <li key={`${p.joiner_id}-${p.assigned_at}`}>
                        <Link
                          to={`/hr/joiners/${p.joiner_id}`}
                          className="block rounded-lg border-l-4 border-success bg-slate-50 p-3 hover:bg-slate-100"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-brand">{p.joiner}</span>
                            {p.band && <Badge tone={p.band === 'Strong' ? 'green' : p.band === 'Weaker' ? 'amber' : 'blue'}>{p.band}</Badge>}
                          </div>
                          <div className="mt-1 text-xs text-slate-500">Induction {pairingDates(p)}</div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {past.length > 0 && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">Joiners before</h3>
                  <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                    {past.map((p) => (
                      <li key={`${p.joiner_id}-${p.assigned_at}`} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
                        <span className="min-w-0">
                          <Link to={`/hr/joiners/${p.joiner_id}`} className="font-medium text-brand hover:underline">{p.joiner}</Link>
                          <span className="block text-xs text-slate-500">{pairingDates(p)}</span>
                        </span>
                        <span className="shrink-0 text-xs text-slate-600">{PAIRING_OUTCOME[p.status]}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {buddy.intro && (
                <section>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">Introduction</h3>
                  <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{buddy.intro}</p>
                </section>
              )}

              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">Working style</h3>
                {buddy.answers.length === 0 ? (
                  <p className="text-sm text-slate-500">Profile not completed yet.</p>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <AnswerTiles answers={buddy.answers} />
                  </div>
                )}
              </section>
            </>
          )}
        </div>

        {buddy && (
          <div className="flex flex-wrap gap-2 border-t border-slate-200 p-4 sm:p-5">
            {buddy.pool_status === 'ACTIVE' && (
              <button className={secondary} onClick={() => act('pause', 'Paused.')}>Pause</button>
            )}
            {buddy.pool_status !== 'ACTIVE' && buddy.pool_status !== 'REMOVED' && completed && (
              <button className={secondary} onClick={() => act('resume', 'Back in the pool.')}>Resume</button>
            )}
            {buddy.pool_status !== 'REMOVED' && !completed && (
              <button className={secondary} onClick={() => act('remind', 'Reminder sent.')}>Send reminder</button>
            )}
            <Link to={`/hr/buddies/${buddy.id}`} className={`${primary} ml-auto`}>Full profile</Link>
          </div>
        )}
      </aside>
    </div>
  )
}
