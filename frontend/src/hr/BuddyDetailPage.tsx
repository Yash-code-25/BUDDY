import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { buddyAction, getBuddy, patchBuddy } from './api'
import type { BuddyDetail } from './api'
import { errorMessage } from '../api'
import { PAIRING_OUTCOME, POOL_TONE, pairingDates, useActions, useFilterOptions } from './helpers'
import { FormField } from './PersonDialog'
import type { FieldSpec } from './PersonDialog'
import { AnswerTiles, Badge, DataView, Field, Notice } from './ui'
import { inputCls, panel, primary, secondary } from '../styles'

const EDIT_FIELDS: FieldSpec[] = [
  ['name', 'Name'], ['email', 'Email'], ['department', 'Department'], ['location', 'Location'],
  ['brand', 'Brand'], ['designation', 'Designation'],
]

// Keyed by id: moving to another record starts with fresh state, and a slow reply for the
// previous one can no longer land on the new page.
export default function BuddyDetailPage() {
  const { id } = useParams()
  return <BuddyDetailPageContent key={id} id={id} />
}

function BuddyDetailPageContent({ id }: { id?: string }) {
  const [buddy, setBuddy] = useState<BuddyDetail | null>(null)
  const [form, setForm] = useState<Record<string, string>>({})
  const [loadedForm, setLoadedForm] = useState<Record<string, string>>({})
  const { error, setError, message, act: run } = useActions()
  const options = useFilterOptions()

  const load = useCallback(() => {
    getBuddy(Number(id))
      .then((b) => {
        const values = Object.fromEntries(
          [...EDIT_FIELDS.map(([k]) => k), 'intro'].map((k) => [k, String(b[k as keyof BuddyDetail] ?? '')]),
        )
        setBuddy(b)
        setForm(values)
        setLoadedForm(values)
      })
      .catch((e) => setError(errorMessage(e, 'Could not load this buddy.')))
  }, [id, setError])

  useEffect(() => {
    load()
  }, [load])

  const save = () =>
    run(async () => {
      await patchBuddy(Number(id), form)
      load()
    }, 'Saved.')

  const unsaved = Object.keys(form).some((k) => form[k] !== loadedForm[k])

  function act(action: string, done: string, confirm?: string) {
    if (confirm && !window.confirm(confirm)) return
    run(async () => {
      // The action reloads the page, so save any edits first rather than lose them.
      if (unsaved) await patchBuddy(Number(id), form)
      await buddyAction(Number(id), action)
      load()
    }, unsaved ? `Changes saved. ${done}` : done)
  }

  if (!buddy) return error ? <Notice>{error}</Notice> : <p className="text-slate-500">Loading…</p>
  const completed = buddy.cmpbd_status === 'completed'
  const outcome = (h: BuddyDetail['history'][number]) => [h.band, PAIRING_OUTCOME[h.status]].filter(Boolean).join(' · ')

  return (
    <div className="space-y-5">
      <Link to="/hr/buddies" className="inline-block text-sm text-brand hover:underline">← Buddies</Link>
      {error && <Notice>{error}</Notice>}
      {message && <Notice kind="ok">{message}</Notice>}

      <section className={panel}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">{buddy.name}</h1>
            <div className="text-sm text-slate-500">{buddy.department} · {buddy.location}</div>
          </div>
          <Badge tone={POOL_TONE[buddy.pool_status] ?? 'slate'}>{buddy.pool_status_label}</Badge>
        </div>
        <div className="mt-2 text-sm text-slate-600">
          {buddy.active_joiners} active · {buddy.total_joiners} joiners in total
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          {buddy.pool_status === 'ACTIVE' && <button className={secondary} onClick={() => act('pause', 'Paused.')}>Pause</button>}
          {buddy.pool_status !== 'ACTIVE' && buddy.pool_status !== 'REMOVED' && (
            <button className={secondary} disabled={!completed} onClick={() => act('resume', 'Resumed.')}>Resume</button>
          )}
          {!completed && <button className={secondary} onClick={() => act('remind', 'Reminder sent.')}>Send reminder</button>}
        </div>

        <details className="mt-3">
          <summary className="min-h-10 cursor-pointer py-2 text-sm font-medium text-brand">More actions</summary>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            {buddy.pool_status !== 'ON_LEAVE' && buddy.pool_status !== 'REMOVED' && (
              <button className={secondary} onClick={() => act('leave', 'Marked on leave.')}>Mark on leave</button>
            )}
            <button className={secondary} onClick={() => act('retake', 'Retake request sent.')}>Request retake</button>
            <button
              className={secondary}
              onClick={() => act('send_login', 'Login details emailed.', `Email ${buddy.name} a new login code?`)}
            >
              Send login details
            </button>
            {completed && (
              <button
                className={secondary}
                onClick={() => act('reset', 'Response reset.', 'Reset this buddy\'s answers? They will need to retake the profile.')}
              >
                Reset response
              </button>
            )}
            {buddy.pool_status !== 'REMOVED' && (
              <button
                className="inline-flex min-h-10 items-center justify-center rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
                onClick={() => act('remove', 'Removed from the pool.', 'Remove this buddy from the pool?')}
              >
                Remove from pool
              </button>
            )}
          </div>
        </details>
      </section>

      <section className={panel}>
        <h2 className="mb-3 font-semibold text-slate-700">Profile answers</h2>
        {buddy.answers.length === 0 ? (
          <p className="text-sm text-slate-500">Not completed yet.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <AnswerTiles answers={buddy.answers} />
            </div>
            <p className="mt-2 text-xs text-slate-400">Submitted {buddy.submitted_at?.slice(0, 10)}</p>
          </>
        )}
      </section>

      <details className={panel}>
        <summary className="cursor-pointer font-semibold text-slate-700">Edit details</summary>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {EDIT_FIELDS.map((spec) => <FormField key={spec[0]} spec={spec} form={form} setForm={setForm} options={options} />)}
        </div>
        <div className="mt-3">
          <Field label="Short introduction (shown to the joiner)">
            <textarea className={inputCls} rows={3} value={form.intro ?? ''} onChange={(e) => setForm({ ...form, intro: e.target.value })} />
          </Field>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button className={primary} disabled={!unsaved} onClick={save}>Save changes</button>
          {unsaved && <span className="text-sm text-amber-700">Unsaved changes</span>}
        </div>
      </details>

      <section>
        <h2 className="mb-3 font-semibold text-slate-700">Joiners they have looked after ({buddy.total_joiners})</h2>
        <DataView
          rows={buddy.history}
          rowKey={(h) => `${h.joiner_id}-${h.assigned_at}`}
          empty="No pairings yet."
          columns={[
            { header: 'Joiner', cell: (h) => <Link className="font-medium text-brand hover:underline" to={`/hr/joiners/${h.joiner_id}`}>{h.joiner}</Link> },
            { header: 'When', cell: (h) => <span className="whitespace-nowrap">{pairingDates(h)}</span> },
            { header: 'Outcome', cell: (h) => <span className="text-slate-600">{outcome(h)}</span> },
          ]}
          card={(h) => (
            <div>
              <Link className="font-semibold text-brand hover:underline" to={`/hr/joiners/${h.joiner_id}`}>{h.joiner}</Link>
              <div className="mt-1 text-xs text-slate-500">{pairingDates(h)}</div>
              <div className="mt-1 text-sm text-slate-600">{outcome(h)}</div>
            </div>
          )}
        />
      </section>
    </div>
  )
}
