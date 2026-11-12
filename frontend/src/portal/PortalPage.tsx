import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { CalendarCheck, HeartHandshake, Home, LogOut, UsersRound } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import Shell from '../EmployeeShell'
import { ApiError, errorMessage } from '../api'
import { confirmAttendance, getMe, retakeProfile, saveInterests, sendReview, signOut, tickInduction } from './api'
import type { BuddyClub, BuddyMe, Club, Induction, Interests, JoinerMe, Me } from './api'
import { primary, secondary } from '../styles'
import { useSubmit } from '../useSubmit'

const date = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : ''

function Card({ title, children, tone, action }: {
  title: string
  children: ReactNode
  tone?: 'success' | 'amber'
  action?: ReactNode
}) {
  // A coloured edge marks what matters: green for your buddy, amber for something to do.
  const edge = tone === 'success' ? 'border-l-4 border-l-success' : tone === 'amber' ? 'border-l-4 border-l-amber-400' : ''
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6 ${edge}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Done({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-slate-700">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-success-soft text-sm text-success">✓</span>
      {children}
    </p>
  )
}

function Progress({ done, total }: { done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 rounded-full bg-slate-100" role="img" aria-label={`${done} of ${total} done`}>
        <div className="h-2 rounded-full bg-success transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="shrink-0 text-sm text-slate-600">{done} of {total} done</span>
    </div>
  )
}

function Steps({ steps }: { steps: { label: string; done: boolean }[] }) {
  const current = steps.findIndex((s) => !s.done)
  return (
    <ol className="grid grid-cols-4 gap-1">
      {steps.map((s, i) => (
        <li key={s.label} className="flex flex-col items-center gap-1.5 text-center">
          <span
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
              s.done ? 'bg-success text-white' : i === current ? 'border-2 border-brand text-brand' : 'bg-slate-100 text-slate-400'
            }`}
          >
            {s.done ? '✓' : i + 1}
          </span>
          <span className={`text-xs leading-tight ${s.done || i === current ? 'text-slate-700' : 'text-slate-400'}`}>{s.label}</span>
        </li>
      ))}
    </ol>
  )
}

/** The 4-week induction as a table, one week at a time. The joiner ticks items; a buddy only reads. */
function InductionTable({ induction, onTick }: { induction: Induction; onTick?: (id: number, done: boolean) => void }) {
  const [week, setWeek] = useState(induction.current_week ?? 1)
  const shown = induction.weeks.find((w) => w.week === week)
  return (
    <div>
      <Progress done={induction.done} total={induction.total} />
      <div className="mt-4 grid grid-cols-4 gap-1 rounded-lg bg-slate-100 p-1" role="tablist" aria-label="Induction weeks">
        {induction.weeks.map((w) => {
          const finished = w.items.length > 0 && w.items.every((i) => i.done)
          return (
            <button
              key={w.week}
              type="button"
              role="tab"
              aria-selected={w.week === week}
              onClick={() => setWeek(w.week)}
              className={`min-h-10 rounded-lg text-sm font-medium ${
                w.week === week ? 'bg-white text-brand shadow-sm' : 'text-slate-600'
              }`}
            >
              Week {w.week}{finished ? ' ✓' : ''}
              {w.week === induction.current_week && <span className="block text-[10px] font-normal text-success">This week</span>}
            </button>
          )
        })}
      </div>
      {shown && shown.items.length === 0 && <p className="mt-4 text-sm text-slate-500">Nothing planned this week.</p>}
      {shown && shown.items.length > 0 && (
        <table className="mt-3 w-full text-left text-sm">
          <thead className="text-xs text-slate-500">
            <tr>
              <th className="py-2 pr-2 font-medium">Day</th>
              <th className="py-2 pr-2 font-medium">Activity</th>
              <th className="hidden py-2 pr-2 font-medium sm:table-cell">With</th>
              <th className="py-2 text-right font-medium">Done</th>
            </tr>
          </thead>
          <tbody>
            {shown.items.map((item) => (
              <tr key={item.id} className="border-t border-slate-100 align-top">
                <td className="whitespace-nowrap py-3 pr-2 text-slate-500">{item.day}</td>
                <td className={`py-3 pr-2 ${item.done ? 'text-slate-400 line-through' : 'text-slate-800'}`}>
                  {item.activity}
                  {item.owner && <span className="block text-xs text-slate-400 no-underline sm:hidden">With {item.owner}</span>}
                </td>
                <td className="hidden py-3 pr-2 text-slate-600 sm:table-cell">{item.owner}</td>
                <td className="py-3 text-right">
                  {onTick ? (
                    <input
                      type="checkbox"
                      className="h-5 w-5 accent-success"
                      checked={item.done}
                      onChange={(e) => onTick(item.id, e.target.checked)}
                      aria-label={`Mark "${item.activity}" as done`}
                    />
                  ) : (
                    <span className={item.done ? 'text-success' : 'text-slate-300'} aria-label={item.done ? 'Done' : 'Not done'}>
                      {item.done ? '✓' : '–'}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function ReviewForm({ review, buddyName, onSent }: {
  review: NonNullable<JoinerMe['review']>
  buddyName: string
  onSent: () => void
}) {
  const [scores, setScores] = useState<number[]>(review.questions.map(() => 0))
  const [comment, setComment] = useState('')
  const { busy, error, run } = useSubmit()

  async function send() {
    if (await run(() => sendReview(scores, comment), 'Could not send your review. Please try again.')) onSent()
  }

  return (
    <div className="space-y-5">
      <p className="text-slate-700">You have finished your 4-week induction. How did {buddyName} help you?</p>
      {review.questions.map((q, qi) => (
        <fieldset key={q}>
          <legend className="mb-2 font-medium text-slate-800">{qi + 1}. {q}</legend>
          <div className="grid grid-cols-5 gap-1.5">
            {review.scale.map((label, i) => {
              const value = i + 1
              const selected = scores[qi] === value
              return (
                <button
                  key={label}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setScores((prev) => prev.map((s, j) => (j === qi ? value : s)))}
                  className={`min-h-12 rounded-lg border-2 px-1 py-2 text-xs leading-tight transition ${
                    selected ? 'border-brand bg-brand text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-brand/50'
                  }`}
                >
                  <span className="block text-base font-semibold">{value}</span>
                  {label}
                </button>
              )
            })}
          </div>
        </fieldset>
      ))}
      <label className="block">
        <span className="mb-1 block font-medium text-slate-800">Anything else? (optional)</span>
        <textarea
          className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-brand"
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </label>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button className={`${primary} w-full`} disabled={busy || scores.includes(0)} onClick={send}>
        {busy ? 'Sending…' : 'Send review'}
      </button>
    </div>
  )
}

/** "Yes, I'll be there", from 3 days before joining, with the Day 1 details the email gave. */
function DayOneCard({ me, onConfirmed }: { me: JoinerMe; onConfirmed: () => void }) {
  const { busy, error, run } = useSubmit()
  const d = me.day_one
  const rows = [
    ['Date', date(me.date_of_joining)],
    ['Arrive by', d.reporting_time],
    ['Address', d.office_address],
    ['Ask for', d.contact_person],
  ].filter(([, v]) => v)

  return (
    <Card title="Your first day" tone={d.confirmed ? 'success' : 'amber'}>
      <dl className="mb-4 space-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex gap-3">
            <dt className="w-24 shrink-0 text-slate-500">{label}</dt>
            <dd className="text-slate-800">{value}</dd>
          </div>
        ))}
        {d.map_link && (
          <div className="flex gap-3">
            <dt className="w-24 shrink-0 text-slate-500">Map</dt>
            <dd><a className="text-brand underline" href={d.map_link} target="_blank" rel="noreferrer">Open the map</a></dd>
          </div>
        )}
      </dl>
      {d.confirmed ? (
        <Done>Thanks! We've noted that you'll be there.</Done>
      ) : (
        <>
          {error && <p className="mb-3 text-sm text-red-700">{error}</p>}
          <button
            className={`${primary} w-full sm:w-auto`}
            disabled={busy}
            onClick={async () => { if (await run(confirmAttendance, 'Could not save that. Please try again.')) onConfirmed() }}
          >
            {busy ? 'Saving…' : "Yes, I'll be there"}
          </button>
        </>
      )}
    </Card>
  )
}

/** "What you enjoy outside work": the second set of questions, kept in the portal only. */
function InterestsCard({ interests, intro, onSaved }: {
  interests: Interests
  intro: string
  onSaved?: () => void // e.g. reload a joiner's clubs
}) {
  const [selected, setSelected] = useState<string[]>(interests.selected)
  const [other, setOther] = useState(interests.other)
  const [saved, setSaved] = useState(false)
  // Once picked, the card shows them on one line; Edit opens the full list again.
  const [editing, setEditing] = useState(interests.selected.length === 0 && !interests.other)
  const { busy, error, run } = useSubmit()
  const toggle = (choice: string) => {
    setSaved(false)
    setSelected((prev) => (prev.includes(choice) ? prev.filter((c) => c !== choice) : [...prev, choice]))
  }

  async function save() {
    if (await run(() => saveInterests(selected, other), 'Could not save that. Please try again.')) {
      setSaved(true)
      if (selected.length > 0 || other.trim()) setEditing(false)
      onSaved?.()
    }
  }

  const picked = [...interests.choices.filter((c) => selected.includes(c)), ...(other.trim() ? [other.trim()] : [])]
  if (!editing) {
    return (
      <Card
        title="What you enjoy outside work"
        action={<button type="button" className={secondary} onClick={() => setEditing(true)}>Edit</button>}
      >
        <div className="flex flex-wrap gap-2">
          {picked.map((p) => (
            <span key={p} className="rounded-full bg-brand-soft px-3 py-1.5 text-sm font-medium text-brand">{p}</span>
          ))}
        </div>
        {saved && <p className="mt-3 text-sm text-success">Saved</p>}
      </Card>
    )
  }

  return (
    <Card title="What you enjoy outside work">
      <p className="mb-3 text-sm text-slate-600">{intro}</p>
      <div className="flex flex-wrap gap-2">
        {interests.choices.map((choice) => {
          const on = selected.includes(choice)
          return (
            <button
              key={choice}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(choice)}
              className={`min-h-10 rounded-full border px-3.5 text-sm transition ${
                on ? 'border-brand bg-brand text-white' : 'border-slate-300 bg-white text-slate-700 hover:border-brand/60'
              }`}
            >
              {choice}
            </button>
          )
        })}
      </div>
      <label className="mt-4 block">
        <span className="mb-1 block text-sm font-medium text-slate-800">Anything else? (optional)</span>
        <input
          className="w-full rounded-lg border border-slate-300 px-4 py-2.5 outline-none focus:border-brand"
          value={other}
          maxLength={300}
          onChange={(e) => { setSaved(false); setOther(e.target.value) }}
        />
      </label>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-4 flex items-center gap-3">
        <button className={primary} disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>
        {saved && <span className="text-sm text-success">Saved</span>}
      </div>
    </Card>
  )
}

/** The joiner's clubs: their interests at their location, and the buddies who share them. */
function ClubsCard({ clubs }: { clubs: Club[] }) {
  const SHOWN = 3
  return (
    <Card title="Your clubs">
      <p className="mb-3 text-sm text-slate-600">Colleagues at your location who enjoy the same things as you.</p>
      <ul className="divide-y divide-slate-100">
        {clubs.map((club) => (
          <li key={club.interest} className="py-3 first:pt-0 last:pb-0">
            <div className="font-medium text-ink">{club.interest} · {club.location}</div>
            <p className="mt-0.5 text-sm text-slate-600">
              {club.buddies.length === 0
                ? 'No one else here yet. You could be the first!'
                : club.buddies.slice(0, SHOWN).map((b) => `${b.name} (${b.department})`).join(', ') +
                  (club.buddies.length > SHOWN ? ` and ${club.buddies.length - SHOWN} more` : '')}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  )
}

type Tab = { key: string; label: string; icon: LucideIcon }
type JoinerTab = 'home' | 'buddy' | 'induction' | 'club'
const JOINER_TABS: (Tab & { key: JoinerTab })[] = [
  { key: 'home', label: 'Home', icon: Home },
  { key: 'buddy', label: 'Buddy', icon: HeartHandshake },
  { key: 'induction', label: 'Induction', icon: CalendarCheck },
  { key: 'club', label: 'Club', icon: UsersRound },
]

type BuddyTab = 'home' | 'joiners' | 'club'
const BUDDY_TABS: (Tab & { key: BuddyTab })[] = [
  { key: 'home', label: 'Home', icon: Home },
  { key: 'joiners', label: 'My joiners', icon: HeartHandshake },
  { key: 'club', label: 'Club', icon: UsersRound },
]

/** The portal's tab, kept in the address (?tab=) so Back and bookmarks work. */
function useTab<K extends string>(tabs: { key: K }[]): [K, (next: K) => void] {
  const [params, setParams] = useSearchParams()
  const asked = params.get('tab')
  const tab = (tabs.some((t) => t.key === asked) ? asked : tabs[0].key) as K
  const setTab = (next: K) => {
    setParams(next === tabs[0].key ? {} : { tab: next })
    window.scrollTo({ top: 0 })
  }
  return [tab, setTab]
}

/** The portal's tabs: under the greeting on a laptop, a bar at the bottom of the screen on a phone.
 * A dot marks a tab with something to do. */
function TabBar<K extends string>({ tabs, tab, setTab, dots }: {
  tabs: (Tab & { key: K })[]
  tab: K
  setTab: (t: K) => void
  dots: Partial<Record<K, boolean>>
}) {
  return (
    <nav
      aria-label="Portal sections"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:static sm:z-auto sm:mb-5 sm:rounded-lg sm:border sm:bg-white sm:p-1 sm:shadow-sm"
    >
      <ul className={`mx-auto grid max-w-2xl sm:gap-1 ${tabs.length === 3 ? 'grid-cols-3' : 'grid-cols-4'}`}>
        {tabs.map(({ key, label, icon: Icon }) => {
          const on = tab === key
          return (
            <li key={key}>
              <button
                type="button"
                aria-current={on ? 'page' : undefined}
                onClick={() => setTab(key)}
                className={`relative flex w-full flex-col items-center gap-0.5 py-2 text-xs font-medium transition sm:flex-row sm:justify-center sm:gap-2 sm:rounded-md sm:py-2.5 sm:text-sm ${
                  on ? 'text-brand sm:bg-brand sm:text-white' : 'text-slate-500 hover:text-ink sm:hover:bg-slate-100'
                }`}
              >
                <span className="relative">
                  <Icon size={20} aria-hidden />
                  {dots[key] && !on && <span className="absolute -right-1 -top-0.5 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-white" aria-label="needs attention" />}
                </span>
                {label}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** A tab with nothing in it yet: one calm line saying what will appear. */
function Empty({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
      {children}
    </section>
  )
}

function JoinerDashboard({ me, reload, setInduction }: {
  me: JoinerMe
  reload: () => void
  setInduction: (i: Induction) => void
}) {
  const [tab, setTab] = useTab(JOINER_TABS)
  const [tickError, setTickError] = useState<string | null>(null)
  const quizDone = me.quiz.status === 'submitted'
  const induction = me.induction
  const review = me.review
  const reviewDue = !!review?.open && !review.submitted

  async function tick(id: number, done: boolean) {
    setTickError(null)
    try {
      setInduction(await tickInduction(id, done))
    } catch (e) {
      setTickError(errorMessage(e, 'Could not save that. Please try again.'))
    }
  }

  const reviewCard = review && me.buddy && (
    <Card title="Rate your buddy" tone={reviewDue ? 'amber' : undefined}>
      {review.submitted ? (
        <Done>Thank you! Your review has been sent.</Done>
      ) : review.open ? (
        <ReviewForm review={review} buddyName={me.buddy.name} onSent={reload} />
      ) : (
        <p className="text-sm text-slate-600">
          After your 4 weeks, three quick questions about your buddy. They open on {date(review.opens_on)}.
        </p>
      )}
    </Card>
  )

  return (
    <div className="pb-20 sm:pb-0">
      <TabBar
        tabs={JOINER_TABS}
        tab={tab}
        setTab={setTab}
        dots={{ home: !quizDone || (me.day_one.show && !me.day_one.confirmed) || reviewDue, club: me.interests.selected.length === 0 }}
      />

      <div className="space-y-4">
        {tab === 'home' && (
          <>
            <Card title="Your buddy programme">
              <Steps
                steps={[
                  { label: 'Answer 5 questions', done: quizDone },
                  { label: 'Buddy assigned', done: !!me.buddy },
                  { label: '4-week induction', done: !!review?.open },
                  { label: 'Rate your buddy', done: !!review?.submitted },
                ]}
              />
              <p className="mt-4 text-center text-sm text-slate-600">{me.stage}</p>
              <p className="mt-1 text-center text-xs text-slate-400">Joining on {date(me.date_of_joining)}</p>
            </Card>

            {!quizDone && (
              <Card title="Your questions" tone="amber">
                {me.quiz.open ? (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-slate-700">Five short questions, about 2 minutes. They help us find your buddy.</p>
                      {me.quiz.due && <p className="mt-1 text-sm font-medium text-amber-700">Please answer by {date(me.quiz.due)}.</p>}
                    </div>
                    <Link to={me.quiz.link} className={primary}>{me.quiz.status === 'in_progress' ? 'Continue' : 'Start'}</Link>
                  </div>
                ) : (
                  <p className="text-slate-700">The questions are closed. Please ask the COMPASS team to reopen them.</p>
                )}
              </Card>
            )}

            {me.day_one.show && <DayOneCard me={me} onConfirmed={reload} />}
            {reviewDue && reviewCard}
          </>
        )}

        {tab === 'buddy' && (
          me.buddy ? (
            <>
              <Card title="Your COMPASS buddy" tone="success">
                <div className="text-xl font-semibold text-ink">{me.buddy.name}</div>
                <div className="text-sm text-slate-600">
                  {[me.buddy.role, me.buddy.department, me.buddy.location].filter(Boolean).join(' · ')}
                </div>
                {me.buddy.intro && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-slate-700">{me.buddy.intro}</p>}
                <p className="mt-4 text-xs text-slate-500">
                  Your buddy from {date(me.buddy.start_date)} to {date(me.buddy.end_date)}
                </p>
              </Card>
              {reviewCard}
            </>
          ) : (
            <Empty>
              {quizDone ? 'We are choosing your buddy. They will appear here once assigned.'
                : 'Answer your 5 questions on Home, and your buddy will appear here once assigned.'}
            </Empty>
          )
        )}

        {tab === 'induction' && (
          induction ? (
            <Card
              title="Your 4-week induction"
              action={induction.current_week === null && (
                <span className="text-xs text-slate-500">Starts {date(induction.start_date)}</span>
              )}
            >
              {tickError && <p className="mb-3 text-sm text-red-700">{tickError}</p>}
              <InductionTable induction={induction} onTick={tick} />
            </Card>
          ) : (
            <Empty>
              Your 4-week induction timetable appears here once your buddy is assigned. It starts on {date(me.date_of_joining)}.
            </Empty>
          )
        )}

        {tab === 'club' && (
          <>
            <InterestsCard
              interests={me.interests}
              intro="Pick your hobbies and interests, so we can tell you about our clubs and teams, from sports to books to cooking."
              onSaved={reload}
            />
            {me.clubs.length > 0 && <ClubsCard clubs={me.clubs} />}
            {me.clubs.length === 0 && me.interests.selected.length > 0 && <Empty>No clubs at your location for these yet.</Empty>}
          </>
        )}
      </div>
    </div>
  )
}

/** One joiner the buddy looks after: who, when, how far along, and the timetable on tap. */
function BuddyJoinerCard({ j }: { j: BuddyMe['joiners'][number] }) {
  const [open, setOpen] = useState(false)
  const week = j.induction.current_week
  return (
    <Card title={j.name} tone="success">
      <div className="-mt-3 text-sm text-slate-600">{[j.role, j.department, j.location].filter(Boolean).join(' · ')}</div>
      <div className="mt-1 text-xs text-slate-500">
        Joins {date(j.date_of_joining)} · your buddy time ends {date(j.end_date)}
      </div>
      <div className="mt-4">
        <div className="mb-1.5 flex items-baseline justify-between text-sm">
          <span className="font-medium text-slate-700">{week ? `Week ${week} of 4` : `Induction starts ${date(j.induction.start_date)}`}</span>
        </div>
        {/* The timetable shows its own bar when open. */}
        {!open && <Progress done={j.induction.done} total={j.induction.total} />}
      </div>
      <button type="button" className={`${secondary} mt-4 w-full sm:w-auto`} aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? 'Hide timetable' : 'Show their timetable'}
      </button>
      {open && <div className="mt-4"><InductionTable induction={j.induction} /></div>}
    </Card>
  )
}

/** New joiners at the buddy's location who share their hobbies: someone to say hello to. */
function BuddyClubsCard({ clubs }: { clubs: BuddyClub[] }) {
  const withJoiners = clubs.filter((c) => c.joiners.length > 0)
  return (
    <Card title="Joiners in your clubs">
      {withJoiners.length === 0 ? (
        <p className="text-sm text-slate-500">No new joiners share your hobbies right now. They appear here when one does.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {withJoiners.map((club) => (
            <li key={club.interest} className="py-3 first:pt-0 last:pb-0">
              <div className="font-medium text-ink">{club.interest} · {club.location}</div>
              <ul className="mt-1 space-y-0.5 text-sm text-slate-600">
                {club.joiners.map((j) => (
                  <li key={j.name + j.date_of_joining}>{j.name} ({j.department}) · joins {date(j.date_of_joining)}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function BuddyDashboard({ me }: { me: BuddyMe }) {
  const navigate = useNavigate()
  const [tab, setTab] = useTab(BUDDY_TABS)
  const { busy, error, run } = useSubmit()
  const profileDone = me.profile.status === 'submitted'
  const next = [...me.joiners].sort((a, b) => a.date_of_joining.localeCompare(b.date_of_joining))[0]

  async function retake() {
    if (!window.confirm('Update your 5 answers? Your profile is reopened with your answers filled in. Until you submit again, you are not suggested for new joiners.')) return
    let link = ''
    if (await run(async () => { link = (await retakeProfile()).link }, 'Could not reopen your profile. Please try again.')) navigate(link)
  }

  return (
    <div className="pb-20 sm:pb-0">
      <TabBar tabs={BUDDY_TABS} tab={tab} setTab={setTab} dots={{ home: !profileDone, club: me.interests.selected.length === 0 }} />

      <div className="space-y-4">
        {tab === 'home' && (
          <>
            <Card title="Your buddy profile" tone={profileDone ? undefined : 'amber'}>
              {profileDone ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Done>Profile complete</Done>
                    <span className="text-sm text-slate-500">Pool status: {me.pool_status_label}</span>
                  </div>
                  {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
                  <button type="button" className={`${secondary} mt-4`} disabled={busy} onClick={retake}>
                    {busy ? 'Opening…' : 'Update my answers'}
                  </button>
                </>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-slate-700">Five short questions so we can match you with joiners who work like you.</p>
                  <Link to={me.profile.link} className={primary}>
                    {me.profile.status === 'in_progress' ? 'Continue' : 'Complete profile'}
                  </Link>
                </div>
              )}
            </Card>

            <div className="grid grid-cols-2 gap-4">
              <Card title="Joiners now">
                <div className="-mt-2 text-3xl font-semibold text-ink">{me.joiners.length}</div>
              </Card>
              <Card title="Buddied in total">
                <div className="-mt-2 text-3xl font-semibold text-ink">{me.total_joiners}</div>
              </Card>
            </div>

            <p className="text-center text-sm text-slate-500">
              {next
                ? <>Next: <span className="font-medium text-ink">{next.name}</span> joins on {date(next.date_of_joining)}.</>
                : 'When a new joiner is assigned to you, they appear under My joiners and you are emailed.'}
            </p>
          </>
        )}

        {tab === 'joiners' && (
          me.joiners.length === 0 ? (
            <Empty>
              None right now. When a new joiner is assigned to you, they appear here and you are emailed.
              {me.total_joiners > 0 && <span className="mt-2 block text-xs text-slate-400">{me.total_joiners} joiners buddied in total. Thank you!</span>}
            </Empty>
          ) : (
            me.joiners.map((j) => <BuddyJoinerCard key={j.name + j.date_of_joining} j={j} />)
          )
        )}

        {tab === 'club' && (
          <>
            <InterestsCard
              interests={me.interests}
              intro="Pick your hobbies and interests. New joiners who enjoy the same things at your location will see you in their clubs."
            />
            {me.interests.selected.length > 0 && <BuddyClubsCard clubs={me.clubs} />}
          </>
        )}
      </div>
    </div>
  )
}

export default function PortalPage() {
  const navigate = useNavigate()
  const [me, setMe] = useState<Me | null>(null)
  const [state, setState] = useState<'loading' | 'signed-out' | 'ready' | 'error'>('loading')

  const reload = useCallback(() => {
    getMe()
      .then((m) => {
        setMe(m)
        setState('ready')
      })
      .catch((e) => setState(e instanceof ApiError && e.status === 403 ? 'signed-out' : 'error'))
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  async function leave() {
    await signOut().catch(() => undefined)
    navigate('/login', { replace: true })
  }

  if (state === 'loading') return <Shell portalLink={false}><p className="text-slate-500">Loading…</p></Shell>
  if (state === 'error') {
    return <Shell portalLink={false}><p className="text-slate-700">Could not load your portal. Please try again.</p></Shell>
  }
  if (state === 'signed-out' || !me) return <Navigate to="/login" replace />

  return (
    <Shell
      portalLink={false}
      plain
      actions={(
        <button type="button" className={secondary} onClick={leave}>
          <LogOut size={16} aria-hidden /> <span className="hidden sm:inline">Sign out</span>
        </button>
      )}
    >
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Hi {me.first_name}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {me.kind === 'joiner' ? 'New joiner' : 'COMPASS buddy'} · {me.username}
        </p>
      </div>
      {me.kind === 'joiner' ? (
        <JoinerDashboard
          me={me}
          reload={reload}
          setInduction={(induction) => setMe({ ...me, induction })}
        />
      ) : (
        <BuddyDashboard me={me} />
      )}
    </Shell>
  )
}
