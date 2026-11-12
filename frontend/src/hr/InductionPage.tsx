import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api'
import { addInductionItem, getInduction, removeInductionItem, saveInductionItem } from './api'
import type { InductionItem } from './api'
import { useLoad } from './helpers'
import { LoadState, PageTitle } from './ui'
import { inputCls, primary, rowAction, secondary } from '../styles'

type Draft = Omit<InductionItem, 'id'>
const WEEKS = [1, 2, 3, 4]
const blank = (week: number): Draft => ({ week, day: '', activity: '', owner: '' })

/** Day, activity and "with whom" inputs, shared by the add row and the edit row. */
function RowFields({ draft, onChange }: { draft: Draft; onChange: (d: Draft) => void }) {
  return (
    <>
      <input className={inputCls} placeholder="Day (e.g. Day 1)" aria-label="Day" value={draft.day}
        onChange={(e) => onChange({ ...draft, day: e.target.value })} />
      <input className={inputCls} placeholder="Activity" aria-label="Activity" value={draft.activity}
        onChange={(e) => onChange({ ...draft, activity: e.target.value })} />
      <input className={inputCls} placeholder="With (e.g. Buddy)" aria-label="With" value={draft.owner}
        onChange={(e) => onChange({ ...draft, owner: e.target.value })} />
    </>
  )
}

function EditRow({ item, onSaved, onCancel }: { item: InductionItem; onSaved: () => void; onCancel: () => void }) {
  const [draft, setDraft] = useState<Draft>(item)
  const [error, setError] = useState<string | null>(null)

  async function save(e: FormEvent) {
    e.preventDefault()
    try {
      await saveInductionItem(item.id, draft)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form onSubmit={save} className="grid gap-2 bg-slate-50 p-3 sm:grid-cols-[8rem_1fr_10rem_6rem_auto]">
      <RowFields draft={draft} onChange={setDraft} />
      <select className={inputCls} aria-label="Week" value={draft.week}
        onChange={(e) => setDraft({ ...draft, week: Number(e.target.value) })}>
        {WEEKS.map((w) => <option key={w} value={w}>Week {w}</option>)}
      </select>
      <div className="flex gap-2">
        <button type="submit" className={primary}>Save</button>
        <button type="button" className={secondary} onClick={onCancel}>Cancel</button>
      </div>
      {error && <p className="text-sm text-red-700 sm:col-span-5">{error}</p>}
    </form>
  )
}

function AddRow({ week, onAdded }: { week: number; onAdded: () => void }) {
  const [draft, setDraft] = useState<Draft>(blank(week))
  const [error, setError] = useState<string | null>(null)

  async function add(e: FormEvent) {
    e.preventDefault()
    try {
      await addInductionItem(draft)
      setDraft(blank(week))
      setError(null)
      onAdded()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form onSubmit={add} className="grid gap-2 border-t border-slate-100 p-3 sm:grid-cols-[8rem_1fr_10rem_auto]">
      <RowFields draft={draft} onChange={setDraft} />
      <button type="submit" className={secondary} disabled={!draft.day.trim() || !draft.activity.trim()}>
        Add row
      </button>
      {error && <p className="text-sm text-red-700 sm:col-span-4">{error}</p>}
    </form>
  )
}

export default function InductionPage() {
  const [editing, setEditing] = useState<number | null>(null)
  const { data: items, error, setError, reload: load } = useLoad(getInduction, 'Could not load the induction programme.')

  async function remove(item: InductionItem) {
    if (!window.confirm(`Remove "${item.activity}"? Joiners who ticked it lose that tick.`)) return
    try {
      await removeInductionItem(item.id)
      load()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <PageTitle title="Induction programme" />
      <LoadState error={error} loading={!items} />

      {items && (
        <div className="space-y-4">
          {WEEKS.map((week) => {
            const rows = items.filter((i) => i.week === week)
            return (
              <section key={week} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <h2 className="flex items-center justify-between bg-slate-50 px-4 py-3 font-semibold text-brand">
                  Week {week}
                  <span className="text-sm font-normal text-slate-500">{rows.length} {rows.length === 1 ? 'item' : 'items'}</span>
                </h2>
                {rows.length > 0 && (
                  <div className="divide-y divide-slate-100">
                    <div className="hidden px-4 py-2 text-xs font-medium text-slate-500 sm:grid sm:grid-cols-[8rem_1fr_10rem_9rem] sm:gap-3">
                      <span>Day</span><span>Activity</span><span>With</span><span />
                    </div>
                    {rows.map((item) =>
                      editing === item.id ? (
                        <EditRow
                          key={item.id}
                          item={item}
                          onCancel={() => setEditing(null)}
                          onSaved={() => {
                            setEditing(null)
                            load()
                          }}
                        />
                      ) : (
                        <div key={item.id} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[8rem_1fr_10rem_9rem] sm:items-center sm:gap-3">
                          <span className="text-slate-500">{item.day}</span>
                          <span className="font-medium text-slate-800">{item.activity}</span>
                          <span className="text-slate-600">{item.owner && <span className="sm:hidden">With </span>}{item.owner}</span>
                          <span className="flex gap-3 sm:justify-end">
                            <button className={rowAction} onClick={() => setEditing(item.id)}>Edit</button>
                            <button className="min-h-10 font-medium text-red-700 hover:text-red-800 hover:underline" onClick={() => remove(item)}>Remove</button>
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                )}
                <AddRow week={week} onAdded={load} />
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
