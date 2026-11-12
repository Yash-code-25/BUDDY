import { useCallback, useMemo, useState } from 'react'
import { StickyNote } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { assignBuddy, getJoinerDetail, joinerAction, saveDayOne } from './api'
import type { Candidate, DayOne, Flag, InductionProgress, JoinerDetail, JoinerNote } from './api'
import { errorMessage } from '../api'
import { BAND_TONE, STATUS_TONE, daysLabel, formatDate, useLoad } from './helpers'
import { AnswerTiles, Badge, Modal, Notice } from './ui'
import { useOpenBuddy } from './useOpenBuddy'
import { useSubmit } from '../useSubmit'
import { inputCls, panel, primary, secondary } from '../styles'

const BAND_STYLE: Record<string, string> = {
  Strong: 'bg-success text-white',
  Good: 'bg-brand text-white',
  Weaker: 'bg-amber-500 text-white',
  'Not suggested': 'bg-slate-300 text-slate-700',
}
const FLAG_STYLE: Record<string, string> = {
  Red: 'bg-red-100 text-red-800',
  Amber: 'bg-amber-100 text-amber-800',
  Info: 'bg-slate-100 text-slate-600',
}
const TIER_LABEL: Record<string, string> = {
  '1': 'Tier 1: Same department, same location',
  '2': 'Tier 2: Same department, other locations',
  '3': 'Tier 3: Other departments, any location',
  weaker: 'Weaker matches (3 of 5)',
}

/** Red and Amber flags are shown as chips. Plain "info" notes are folded into one quiet line. */
function FlagChips({ flags }: { flags: Flag[] }) {
  const important = flags.filter((f) => f.level !== 'Info')
  const info = flags.filter((f) => f.level === 'Info')
  if (flags.length === 0) return <span className="text-xs text-slate-400">No flags</span>
  return (
    <div className="space-y-1.5">
      {important.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {important.map((f, i) => (
            <span key={i} className={`rounded-full px-2.5 py-1 text-xs ${FLAG_STYLE[f.level]}`}>
              {f.level}: {f.text}
            </span>
          ))}
        </div>
      )}
      {info.length > 0 && <div className="text-xs text-slate-400">{info.map((f) => f.text).join(' · ')}</div>}
    </div>
  )
}

/** The joiner's 4-week induction at a glance: how much they have ticked, week by week. */
function InductionSummary({ induction }: { induction: InductionProgress }) {
  const pct = induction.total ? Math.round((induction.done / induction.total) * 100) : 0
  return (
    <div className="mt-4 rounded-lg bg-slate-50 p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium text-slate-700">Induction: {induction.done} of {induction.total} done</span>
        <span className="text-slate-500">
          {induction.current_week ? `Week ${induction.current_week} of 4` : `Starts ${formatDate(induction.start_date)}`}
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-200" role="img" aria-label={`${pct}% of the induction done`}>
        <div className="h-2 rounded-full bg-success" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-2 grid grid-cols-4 gap-2 text-center text-xs text-slate-500">
        {induction.weeks.map((w) => (
          <span key={w.week}>
            Week {w.week}: {w.items.filter((i) => i.done).length}/{w.items.length}
          </span>
        ))}
      </div>
    </div>
  )
}

function CandidateCard(props: {
  c: Candidate
  isTop: boolean
  canAct: boolean
  onCompare: () => void
  onChoose: () => void
}) {
  const { c, isTop, canAct, onCompare, onChoose } = props
  return (
    <div className={`rounded-lg border bg-white p-4 ${isTop ? 'border-success' : 'border-slate-200'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold">{c.name}</div>
          <div className="text-sm text-slate-500">{c.department} · {c.location}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${BAND_STYLE[c.band]}`}>{c.band}</span>
          {isTop && <span className="text-xs font-medium text-success">Top pick</span>}
        </div>
      </div>
      <div className="mt-3 text-sm text-slate-600">
        <b>{c.close_count} of 5</b> close · {c.active_joiners} active, {c.total_joiners} total joiners
      </div>
      <div className="mt-2"><FlagChips flags={c.flags} /></div>
      <div className="mt-4 flex gap-2">
        <button className={`${secondary} flex-1 sm:flex-none`} onClick={onCompare}>Compare</button>
        {canAct && <button className={`${primary} flex-1 sm:flex-none`} onClick={onChoose}>Assign buddy</button>}
      </div>
    </div>
  )
}

// How far apart one answer is: close, different (an Amber flag) or very different (a Red flag).
const GAP_STYLE = {
  close: { label: 'Close', chip: 'bg-success-soft text-emerald-700 ring-emerald-200', edge: 'border-l-success' },
  different: { label: 'Different', chip: 'bg-amber-50 text-amber-800 ring-amber-200', edge: 'border-l-amber-400' },
  far: { label: 'Very different', chip: 'bg-rose-50 text-rose-700 ring-rose-200', edge: 'border-l-rose-500' },
  slight: { label: 'Slightly different', chip: 'bg-slate-100 text-slate-600 ring-slate-200', edge: 'border-l-slate-300' },
}

/** The joiner's and the buddy's answers side by side, one question per row, so the differences jump out. */
function CompareDialog(props: { detail: JoinerDetail; c: Candidate; onClose: () => void; onChoose?: () => void }) {
  const { detail, c, onClose, onChoose } = props
  const labelFor = (qNumber: number, value: number) =>
    detail.questions.find((q) => q.number === qNumber)?.options.find((o) => o.value === value)?.label ?? ''
  const joinerFirst = detail.joiner.name.split(' ')[0]
  const buddyFirst = c.name.split(' ')[0]

  return (
    <Modal onClose={onClose} wide>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-ink">Compare working styles</h3>
          <p className="mt-0.5 text-sm text-slate-500">{detail.joiner.name} (joiner) and {c.name} (buddy)</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={BAND_TONE[c.band] ?? 'slate'}>{c.band}</Badge>
          <span className="text-sm font-medium text-slate-700">{c.close_count} of 5 close</span>
        </div>
      </div>

      {/* laptop: the names head the two answer columns */}
      <div className="mt-5 hidden grid-cols-[9rem_1fr_1fr] gap-4 px-4 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 sm:grid">
        <span>Question</span>
        <span>{joinerFirst}</span>
        <span>{buddyFirst}</span>
      </div>

      <div className="mt-4 space-y-2 sm:mt-0">
        {detail.answers.map((a, i) => {
          const flag = c.flags.find((f) => f.question === a.number)
          const kind = flag?.level === 'Red' ? 'far' : flag?.level === 'Amber' ? 'different'
            : c.gaps[i] <= detail.settings.close_gap ? 'close' : 'slight'
          const style = GAP_STYLE[kind]
          return (
            <div
              key={a.number}
              className={`grid gap-x-4 gap-y-2 rounded-lg border border-l-4 border-slate-200 bg-white px-4 py-3 text-sm sm:grid-cols-[9rem_1fr_1fr] sm:items-center ${style.edge}`}
            >
              <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-start sm:gap-1">
                <span className="font-semibold text-ink">{a.dimension}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style.chip}`}>{style.label}</span>
              </div>
              <div>
                <span className="block text-xs text-slate-500 sm:hidden">{joinerFirst}</span>
                <span className="text-slate-800">{a.label}</span>
              </div>
              <div>
                <span className="block text-xs text-slate-500 sm:hidden">{buddyFirst}</span>
                <span className="text-slate-800">{labelFor(a.number, c.answers[i])}</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button className={secondary} onClick={onClose}>Close</button>
        {onChoose && <button className={primary} onClick={onChoose}>Assign this buddy</button>}
      </div>
    </Modal>
  )
}

function AssignDialog(props: {
  detail: JoinerDetail
  c: Candidate
  topId: string | null
  onClose: () => void
  onDone: () => void
}) {
  const { detail, c, topId, onClose, onDone } = props
  const changing = detail.pairing !== null
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const { busy, error, run } = useSubmit()

  const why: string[] = []
  if (c.buddy_id !== topId) why.push(topId ? 'This is not the top suggestion.' : 'There is no system suggestion.')
  if (c.band === 'Weaker') why.push('This is a Weaker match.')
  if (c.flags.some((f) => f.level === 'Red')) why.push('This buddy has a Red flag.')
  const needsReason = why.length > 0
  const ready = !needsReason || (reason !== '' && (reason !== 'Other' || note.trim() !== ''))

  async function submit() {
    if (await run(() => assignBuddy(detail.joiner.id, { buddy_id: c.buddy_id, reason, note }), 'Could not assign the buddy.')) {
      onDone()
    }
  }

  return (
    <Modal onClose={onClose}>
      <h3 className="mb-1 text-lg font-semibold text-ink">{changing ? 'Change buddy' : 'Assign buddy'}</h3>
      <p className="mb-1 text-sm text-slate-600">
        Assign <b>{c.name}</b> to <b>{detail.joiner.name}</b> ({c.band}, {c.close_count} of 5 close).
      </p>
      <p className="mb-4 text-sm text-slate-500">
        {changing
          ? `${detail.pairing?.buddy_name} is told they are no longer needed. ${c.name} and the joiner are emailed straight away.`
          : 'The buddy and the joiner are emailed straight away. Nobody has to accept.'}
      </p>
      {error && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {needsReason && (
        <div className="mb-4">
          <ul className="mb-3 list-disc pl-5 text-sm text-amber-800">{why.map((w) => <li key={w}>{w}</li>)}</ul>
          <label className="mb-1 block text-sm text-slate-600">Reason (required)</label>
          <select
            className={inputCls}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            <option value="">Choose a reason…</option>
            {detail.reasons.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          {reason === 'Other' && (
            <textarea
              className={`${inputCls} mt-2`}
              rows={3}
              placeholder="Add a note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          )}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button className={secondary} onClick={onClose}>Cancel</button>
        <button className={primary} disabled={!ready || busy} onClick={submit}>
          {busy ? 'Saving…' : changing ? 'Change buddy' : 'Assign buddy'}
        </button>
      </div>
    </Modal>
  )
}

function noteWhen({ date, time }: JoinerNote) {
  if (!date) return ''
  const day = new Date(`${date}T00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  return time ? `${day}, ${time}` : day
}

/** The admins' notes on a joiner, newest first, as small cards. */
function Notes({ notes }: { notes: JoinerNote[] }) {
  if (notes.length === 0) return null
  return (
    <section className="mt-4">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
        <StickyNote className="h-4 w-4 text-slate-400" aria-hidden />
        Notes
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">{notes.length}</span>
      </h3>
      <ul className="space-y-2">
        {notes.map((n, i) => (
          <li key={i} className="flex gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand/10 text-xs font-semibold text-brand" aria-hidden>
              A
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-semibold text-ink">Admin</span>
                <time className="text-xs text-slate-400" dateTime={n.date}>{noteWhen(n)}</time>
              </div>
              <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-slate-700">{n.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function JoinerActions({ detail, onDone }: { detail: JoinerDetail; onDone: () => void }) {
  const { joiner } = detail
  const status = joiner.status
  const submitted = detail.answers.length > 0
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [noteFor, setNoteFor] = useState<'note' | 'not_required' | null>(null)
  const [note, setNote] = useState('')

  async function run(action: string, done: string, text = '') {
    try {
      await joinerAction(joiner.id, action, text)
      setMessage({ ok: true, text: done })
      setNoteFor(null)
      setNote('')
      onDone()
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) })
    }
  }

  const open = ['AWAITING_ASSESSMENT', 'AWAITING_PAIRING', 'MANUAL', 'ON_HOLD']
  return (
    <div className="mt-4 border-t border-slate-100 pt-4">
      {message && <Notice kind={message.ok ? 'ok' : 'error'}>{message.text}</Notice>}
      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
        {!submitted && ['AWAITING_ASSESSMENT', 'MANUAL'].includes(status) && (
          <button className={secondary} onClick={() => run('remind', 'Reminder emailed to the joiner.')}>Send reminder</button>
        )}
        {['AWAITING_ASSESSMENT', 'AWAITING_PAIRING', 'ON_HOLD'].includes(status) && (
          <button className={secondary} onClick={() => run('manual', 'Routed to manual pairing.')}>Route to manual</button>
        )}
        {['AWAITING_ASSESSMENT', 'AWAITING_PAIRING', 'MANUAL'].includes(status) && (
          <button className={secondary} onClick={() => run('hold', 'Put on hold.')}>Put on hold</button>
        )}
        {status === 'ON_HOLD' && <button className={secondary} onClick={() => run('release', 'Released from hold.')}>Release</button>}
        {open.includes(status) && <button className={secondary} onClick={() => setNoteFor('not_required')}>Buddy not required</button>}
        <button className={secondary} onClick={() => setNoteFor('note')}>Add note</button>
        <button
          className={secondary}
          onClick={() => window.confirm(`Email ${joiner.name} their username and password again?`) &&
            run('send_login', 'Login details emailed to the joiner.')}
        >
          Send login details
        </button>
      </div>
      <Notes notes={joiner.notes} />

      {noteFor && (
        <Modal onClose={() => setNoteFor(null)}>
          <h3 className="mb-3 text-lg font-semibold text-ink">
            {noteFor === 'note' ? 'Add a note' : 'Buddy not required'}
          </h3>
          {noteFor === 'not_required' && (
            <p className="mb-3 text-sm text-slate-600">
              For a rehire or internal transfer. The joiner is closed in COMPASS.
            </p>
          )}
          <textarea
            className={inputCls}
            rows={4}
            placeholder={noteFor === 'note' ? 'Write your note' : 'Reason (optional)'}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="mt-4 flex justify-end gap-2">
            <button className={secondary} onClick={() => setNoteFor(null)}>Cancel</button>
            <button
              className={primary}
              disabled={noteFor === 'note' && !note.trim()}
              onClick={() => run(noteFor, noteFor === 'note' ? 'Note added.' : 'Closed: buddy not required.', note)}
            >
              Save
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

const DAY_ONE_FIELDS: [keyof DayOne, string][] = [
  ['manager_name', 'Manager'],
  ['reporting_time', 'Reporting time'],
  ['contact_person', 'Ask for (at reception)'],
  ['directions', 'Getting there'],
]

/** The joiner's Day 1 details for the pre-joining emails, and whether they confirmed they'll be there. */
function DayOnePanel({ joiner, onSaved }: { joiner: JoinerDetail['joiner']; onSaved: () => void }) {
  const [form, setForm] = useState<DayOne | null>(null)
  const { busy, error, run } = useSubmit()

  async function save() {
    if (form && (await run(() => saveDayOne(joiner.id, form), 'Could not save the Day 1 details.'))) {
      setForm(null)
      onSaved()
    }
  }

  return (
    <section className={panel}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-ink">Day 1 and pre-joining emails</h2>
        {joiner.attendance_confirmed_at ? (
          <Badge tone="green">
            Confirmed they'll be there · {new Date(joiner.attendance_confirmed_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
          </Badge>
        ) : (
          <Badge tone="slate">Not confirmed yet</Badge>
        )}
      </div>
      {form ? (
        <>
          {error && <Notice>{error}</Notice>}
          <div className="grid gap-3 sm:grid-cols-2">
            {DAY_ONE_FIELDS.map(([key, label]) => (
              <label key={key} className="block text-sm">
                <span className="mb-1 block font-medium text-slate-700">{label}</span>
                <input className={inputCls} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
              </label>
            ))}
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button className={secondary} onClick={() => setForm(null)}>Cancel</button>
            <button className={primary} disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>
          </div>
        </>
      ) : (
        <>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {DAY_ONE_FIELDS.map(([key, label]) => (
              <div key={key} className="flex gap-2">
                <dt className="w-40 shrink-0 text-slate-500">{label}</dt>
                <dd className="min-w-0 break-words text-slate-800">{joiner[key] || <span className="text-slate-400">Not set</span>}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            Blank details are left out of the emails. The office address and map link for {joiner.location} are set
            in Settings.
          </p>
          <button
            className={`${secondary} mt-3`}
            onClick={() => setForm(Object.fromEntries(DAY_ONE_FIELDS.map(([k]) => [k, joiner[k]])) as DayOne)}
          >
            Edit Day 1 details
          </button>
        </>
      )}
    </section>
  )
}

// Keyed by id: moving to another record starts with fresh state, and a slow reply for the
// previous one can no longer land on the new page.
export default function MatchReviewPage() {
  const { id } = useParams()
  return <MatchReviewPageContent key={id} id={id} />
}

function MatchReviewPageContent({ id }: { id?: string }) {
  const [visible, setVisible] = useState(1)
  const [moreOpen, setMoreOpen] = useState<Record<string, boolean>>({})
  const [compare, setCompare] = useState<Candidate | null>(null)
  const [choice, setChoice] = useState<Candidate | null>(null)
  const [showManual, setShowManual] = useState(false)
  const [search, setSearch] = useState('')
  const [changing, setChanging] = useState(false)
  const openBuddy = useOpenBuddy()

  const { data: detail, error, reload: load } = useLoad(
    useCallback(() => getJoinerDetail(Number(id)), [id]), 'Could not load this joiner.')

  const run = detail?.run ?? null
  const groups = useMemo(() => {
    if (!run) return []
    return [
      { key: '1', list: run.tiers['1'] ?? [] },
      { key: '2', list: run.tiers['2'] ?? [] },
      { key: '3', list: run.tiers['3'] ?? [] },
      { key: 'weaker', list: run.weaker },
    ].filter((g) => g.list.length > 0)
  }, [run])

  if (error) return <p className="text-red-700">{error}</p>
  if (!detail) return <p className="text-slate-500">Loading…</p>

  const { joiner, answers, pairing } = detail
  const perTier = detail.settings.candidates_per_tier
  const topId = run && run.shown.length > 0 ? run.shown[0].buddy_id : null
  const canAct = pairing ? pairing.can_change && changing : joiner.status === 'AWAITING_PAIRING' || joiner.status === 'MANUAL'
  const manualOpen = showManual || run?.tier_reached === 'MANUAL'
  const eligible = (run?.scored ?? []).filter((c) => c.name.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="space-y-5">
      <Link to="/hr/joiners" className="inline-block text-sm text-brand hover:underline">← Joiners</Link>

      <section className={panel}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">{joiner.name}</h1>
            <div className="text-sm text-slate-500">
              {joiner.department} · {joiner.location} · joins {formatDate(joiner.date_of_joining)} ({daysLabel(joiner.days_to_joining)})
            </div>
            <div className="mt-0.5 text-xs text-slate-400">
              {[joiner.candidate_id, joiner.designation, joiner.personal_email].filter(Boolean).join(' · ')}
            </div>
          </div>
          <Badge tone={STATUS_TONE[joiner.status] ?? 'slate'}>{joiner.status_label}</Badge>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <AnswerTiles answers={answers} />
          {answers.length === 0 && <p className="text-sm text-slate-500">No answers submitted yet.</p>}
        </div>
        <JoinerActions detail={detail} onDone={load} />
      </section>

      <DayOnePanel joiner={joiner} onSaved={load} />

      {pairing && (
        <section className="rounded-lg border border-success/40 bg-white p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-success">Buddy assigned</div>
              <button type="button" className="text-lg font-semibold text-ink underline" onClick={() => openBuddy(pairing.buddy_pk)}>
                {pairing.buddy_name}
              </button>
              <div className="text-sm text-slate-500">
                {pairing.band} · {pairing.source.toLowerCase().replace('_', ' ')} · induction {formatDate(pairing.start_date)} to {formatDate(pairing.end_date)}
              </div>
              {pairing.override_reason && <div className="mt-1 text-sm text-slate-600">Reason: {pairing.override_reason}</div>}
            </div>
            {pairing.can_change && (
              <button className={changing ? primary : secondary} onClick={() => setChanging(!changing)}>
                {changing ? 'Keep this buddy' : 'Change buddy'}
              </button>
            )}
          </div>
          {changing && (
            <p className="mt-3 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Choose the new buddy below. You can change the buddy only within 2 days of assigning.
            </p>
          )}
          {detail.induction && <InductionSummary induction={detail.induction} />}
          <p className="mt-3 text-sm text-slate-600">
            Buddy review: {pairing.reviewed ? 'received, see Reports.' : `opens on ${formatDate(pairing.review_opens_on)}.`}
          </p>
        </section>
      )}

      {!run && (
        <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-5 text-center text-sm text-slate-500">
          No match yet. Buddy suggestions appear here once the joiner answers their 5 questions.
        </p>
      )}

      {run && groups.length === 0 && (
        <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No suggested matches (nothing at 3 of 5 or better). Use manual search below.
        </p>
      )}

      {groups.slice(0, visible).map((g) => {
        const open = moreOpen[g.key]
        const list = open ? g.list : g.list.slice(0, perTier)
        return (
          <section key={g.key}>
            <h2 className="mb-3 font-semibold text-slate-700">
              {TIER_LABEL[g.key]} <span className="font-normal text-slate-500">· {g.list.length} matches found</span>
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {list.map((c) => (
                <CandidateCard
                  key={c.buddy_id}
                  c={c}
                  isTop={c.buddy_id === topId}
                  canAct={canAct}
                  onCompare={() => setCompare(c)}
                  onChoose={() => setChoice(c)}
                />
              ))}
            </div>
            {g.list.length > perTier && (
              <button className="mt-3 text-sm font-medium text-brand hover:underline" onClick={() => setMoreOpen({ ...moreOpen, [g.key]: !open })}>
                {open ? 'Show fewer' : `Show more (${g.list.length - perTier})`}
              </button>
            )}
          </section>
        )
      })}

      {visible < groups.length && (
        <button className={secondary} onClick={() => setVisible(visible + 1)}>Expand search</button>
      )}

      {run && (
        <section className={panel}>
          <button className="min-h-10 font-medium text-brand" onClick={() => setShowManual(!manualOpen)}>
            {manualOpen ? '▾' : '▸'} Search all eligible buddies ({run.scored.length})
          </button>
          {manualOpen && (
            <div className="mt-3">
              <input
                className={`${inputCls} mb-3`}
                placeholder="Search by name"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <div className="divide-y divide-slate-100">
                {eligible.map((c) => (
                  <div key={c.buddy_id} className={`py-3 ${c.band === 'Not suggested' ? 'opacity-60' : ''}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-medium">{c.name}</div>
                        <div className="text-xs text-slate-500">{c.department} · {c.location}</div>
                      </div>
                      <span className="whitespace-nowrap text-xs text-slate-600">
                        {`${c.band} · ${c.close_count} of 5`}
                      </span>
                    </div>
                    <div className="mt-2 flex gap-2">
                      <button className={`${secondary} flex-1 sm:flex-none`} onClick={() => setCompare(c)}>Compare</button>
                      {canAct && <button className={`${primary} flex-1 sm:flex-none`} onClick={() => setChoice(c)}>Assign buddy</button>}
                    </div>
                  </div>
                ))}
                {eligible.length === 0 && <p className="py-3 text-sm text-slate-500">No eligible buddies found.</p>}
              </div>
            </div>
          )}
        </section>
      )}

      {compare && (
        <CompareDialog
          detail={detail}
          c={compare}
          onClose={() => setCompare(null)}
          onChoose={canAct ? () => {
            setChoice(compare)
            setCompare(null)
          } : undefined}
        />
      )}
      {choice && (
        <AssignDialog
          detail={detail}
          c={choice}
          topId={topId}
          onClose={() => setChoice(null)}
          onDone={() => {
            setChoice(null)
            setChanging(false)
            load()
          }}
        />
      )}
    </div>
  )
}
