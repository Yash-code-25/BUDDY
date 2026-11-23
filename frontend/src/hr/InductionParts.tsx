import { useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CheckCircle2, Circle } from 'lucide-react'
import { errorMessage } from '../api'
import { saveInductionItem } from './api'
import type { InductionDraft, InductionItem, InductionJoiner, InductionProgress } from './api'
import { joiningMonth, optionList, useFilterOptions } from './helpers'
import { FilterBar } from './ui'
import { inputCls, primary, secondary } from '../styles'

const WEEKS = [1, 2, 3, 4]
const blankRow = (week: number): InductionDraft => ({ week, day: '', activity: '', owner: '' })

/** Day, activity and "with whom" inputs, shared by the add row and the edit row. */
function RowFields({ draft, onChange, dayHint }: { draft: InductionDraft; onChange: (d: InductionDraft) => void; dayHint: string }) {
  return (
    <>
      <input className={inputCls} placeholder={dayHint} aria-label="Day" value={draft.day}
        onChange={(e) => onChange({ ...draft, day: e.target.value })} />
      <input className={inputCls} placeholder="Activity" aria-label="Activity" value={draft.activity}
        onChange={(e) => onChange({ ...draft, activity: e.target.value })} />
      <input className={inputCls} placeholder="With (e.g. Buddy)" aria-label="With" value={draft.owner}
        onChange={(e) => onChange({ ...draft, owner: e.target.value })} />
    </>
  )
}

/** Edit one row in place. A joiner's own row can also move to another week; a common Day 1 row cannot. */
export function EditRow({ item, canMove, joinerId, onSaved, onCancel }: {
  item: InductionItem
  canMove: boolean
  joinerId?: number // on a joiner's page: a common Day 1 row is changed for them alone
  onSaved: () => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState<InductionDraft>(item)
  const [error, setError] = useState<string | null>(null)

  async function save(e: FormEvent) {
    e.preventDefault()
    try {
      await saveInductionItem(item.id, draft, joinerId)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form onSubmit={save}
      className={`grid gap-2 bg-slate-50 p-3 ${canMove ? 'sm:grid-cols-[8rem_1fr_10rem_6rem_auto]' : 'sm:grid-cols-[8rem_1fr_10rem_auto]'}`}>
      <RowFields draft={draft} onChange={setDraft} dayHint="Day" />
      {canMove && (
        <select className={inputCls} aria-label="Week" value={draft.week}
          onChange={(e) => setDraft({ ...draft, week: Number(e.target.value) })}>
          {WEEKS.map((w) => <option key={w} value={w}>Week {w}</option>)}
        </select>
      )}
      <div className="flex gap-2">
        <button type="submit" className={primary}>Save</button>
        <button type="button" className={secondary} onClick={onCancel}>Cancel</button>
      </div>
      {error && <p className="text-sm text-red-700 sm:col-span-full">{error}</p>}
    </form>
  )
}

/** The empty row under a table that adds a new row to it. */
export function AddRow({ week, dayHint, onAdd }: { week: number; dayHint: string; onAdd: (d: InductionDraft) => Promise<unknown> }) {
  const [draft, setDraft] = useState<InductionDraft>(blankRow(week))
  const [error, setError] = useState<string | null>(null)

  async function add(e: FormEvent) {
    e.preventDefault()
    try {
      await onAdd(draft)
      setDraft(blankRow(week))
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form onSubmit={add} className="grid gap-2 border-t border-slate-100 p-3 sm:grid-cols-[8rem_1fr_10rem_auto]">
      <RowFields draft={draft} onChange={setDraft} dayHint={dayHint} />
      <button type="submit" className={secondary} disabled={!draft.day.trim() || !draft.activity.trim()}>
        Add row
      </button>
      {error && <p className="text-sm text-red-700 sm:col-span-4">{error}</p>}
    </form>
  )
}

/** Search, department, location, joining month and buddy: the same filters on the Induction page
 *  and the Induction progress report. */
export function InductionFilters({ rows, params, onChange }: {
  rows: InductionJoiner[]
  params: URLSearchParams
  onChange: (next: URLSearchParams) => void
}) {
  const options = useFilterOptions()
  const months = [...new Set([...rows].sort((a, b) => a.date_of_joining.localeCompare(b.date_of_joining))
    .map((r) => joiningMonth(r.date_of_joining)))]
  return (
    <FilterBar
      params={params}
      onChange={onChange}
      fields={[
        { key: 'q', label: 'Search by name or ID', type: 'text' },
        { key: 'department', label: 'Department', type: 'select', options: optionList(options.department) },
        { key: 'location', label: 'Location', type: 'select', options: optionList(options.location) },
        { key: 'month', label: 'Joining month', type: 'select', options: optionList(months) },
        { key: 'buddy', label: 'Buddy', type: 'select', options: [{ value: 'yes', label: 'Has a buddy' }, { value: 'no', label: 'No buddy yet' }] },
      ]}
    />
  )
}

/** How much of the induction is ticked, as a bar and a number. */
export function PercentBar({ percent, done, total }: { percent: number; done: number; total: number }) {
  return (
    <div className="min-w-32">
      <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
        <span className="font-semibold text-ink">{percent}%</span>
        <span className="text-slate-500">{done} of {total}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-200" role="img" aria-label={`${percent}% of the induction done`}>
        <div className="h-2 rounded-full bg-success" style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

/** Ticked or not, as the joiner left it. */
export function DoneMark({ done }: { done: boolean }) {
  return done ? (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs font-semibold text-success">
      <Check size={14} aria-hidden /> Done
    </span>
  ) : (
    <span className="whitespace-nowrap text-xs text-slate-400">Not yet</span>
  )
}

/** A joiner's whole plan, read only, with what they have ticked: the Induction progress report. Each
 *  week is a card with its own progress; a ticked item has a green check. */
export function PlanView({ induction }: { induction: InductionProgress }) {
  return (
    <div className="space-y-4">
      {induction.weeks.map((w) => {
        const done = w.items.filter((i) => i.done).length
        const pct = w.items.length ? Math.round((done * 100) / w.items.length) : 0
        const current = w.week === induction.current_week
        return (
          <section key={w.week} className={`overflow-hidden rounded-xl border ${current ? 'border-brand/40' : 'border-slate-200'}`}>
            <header className="flex items-center gap-3 border-b border-slate-100 bg-slate-50 px-4 py-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-sm font-bold text-brand">
                {w.week}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold text-ink">Week {w.week}</h3>
                  {current && (
                    <span className="rounded-full bg-brand px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">This week</span>
                  )}
                </div>
                <div className="mt-1 h-1.5 max-w-40 rounded-full bg-slate-200">
                  <div className="h-1.5 rounded-full bg-success" style={{ width: `${pct}%` }} />
                </div>
              </div>
              <span className="shrink-0 text-sm text-slate-500">
                <span className="font-semibold text-ink">{done}</span> / {w.items.length} done
              </span>
            </header>
            {w.items.length === 0 ? (
              <p className="px-4 py-4 text-sm italic text-slate-400">Nothing planned this week.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {w.items.map((i) => (
                  <li key={i.id} className="flex gap-3 px-4 py-3">
                    {i.done
                      ? <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-success" aria-label="Done" />
                      : <Circle size={20} className="mt-0.5 shrink-0 text-slate-300" aria-label="Not done yet" />}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="break-words text-xs font-semibold uppercase tracking-wide text-slate-500">{i.day}</span>
                        {i.common && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">Common Day 1</span>}
                      </div>
                      <p className={`mt-0.5 break-words text-sm ${i.done ? 'text-slate-500' : 'font-medium text-slate-800'}`}>{i.activity}</p>
                      {i.owner && <p className="mt-0.5 break-words text-xs text-slate-500">With {i.owner}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}
